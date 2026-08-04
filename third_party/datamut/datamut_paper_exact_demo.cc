#include "datamut_analysis.h"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <functional>
#include <iomanip>
#include <iostream>
#include <limits>
#include <map>
#include <memory>
#include <random>
#include <set>
#include <sstream>
#include <string>
#include <utility>
#include <vector>

namespace
{

using NodeId = datamut::NodeId;
using PacketId = datamut::PacketId;

struct PacketOutcome
{
    datamut::RoutePlan route;
    datamut::PacketLogger logger;
    std::vector<std::string> missedOpportunities;
};

static datamut::RoutePlan
ReplayRoutePlan(const datamut::TimeWindowGraph& graph, const datamut::RoutePlan& templatePlan, double startTime)
{
    datamut::RoutePlan replayed;
    if (!templatePlan.reachable || templatePlan.steps.empty())
    {
        return replayed;
    }

    replayed.reachable = true;
    replayed.steps.reserve(templatePlan.steps.size());

    double currentTime = startTime;
    replayed.steps.push_back({templatePlan.steps.front().node, currentTime, templatePlan.steps.front().encounterWindowId});

    for (std::size_t i = 1; i < templatePlan.steps.size(); ++i)
    {
        const auto& templateStep = templatePlan.steps[i];
        const datamut::EncounterWindow* window = graph.FindWindow(templateStep.encounterWindowId);
        if (window == nullptr)
        {
            replayed.reachable = false;
            replayed.steps.clear();
            replayed.totalArrivalTime = std::numeric_limits<double>::infinity();
            return replayed;
        }

        currentTime = graph.NextContactTime(currentTime, *window);
        replayed.steps.push_back({templateStep.node, currentTime, templateStep.encounterWindowId});
    }

    replayed.totalArrivalTime = currentTime;
    return replayed;
}

class DelayModel
{
  public:
    DelayModel(double benignMin,
               double benignMax,
               double maliciousMin,
               double maliciousMax,
               std::set<NodeId> maliciousNodes,
               std::uint32_t seed,
               double propagationDelay)
        : m_benignMin(benignMin),
          m_benignMax(benignMax),
          m_maliciousMin(maliciousMin),
          m_maliciousMax(maliciousMax),
          m_maliciousNodes(std::move(maliciousNodes)),
          m_seed(seed),
          m_propagationDelay(propagationDelay)
    {
    }

    double BenignDelay(NodeId nodeId, PacketId packetId, std::size_t hopIndex) const
    {
        return Sample(Mix(packetId, nodeId, hopIndex, 0x11u), m_benignMin, m_benignMax);
    }

    double MaliciousExtraDelay(NodeId nodeId, PacketId packetId, std::size_t hopIndex) const
    {
        if (!IsMalicious(nodeId))
        {
            return 0.0;
        }

        return Sample(Mix(packetId, nodeId, hopIndex, 0x29u), m_maliciousMin, m_maliciousMax);
    }

    bool IsMalicious(NodeId nodeId) const
    {
        return m_maliciousNodes.find(nodeId) != m_maliciousNodes.end();
    }

    double PropagationDelay() const
    {
        return m_propagationDelay;
    }

  private:
    std::uint64_t Mix(PacketId packetId, NodeId nodeId, std::size_t hopIndex, std::uint64_t salt) const
    {
        std::uint64_t value = static_cast<std::uint64_t>(packetId);
        value ^= (static_cast<std::uint64_t>(nodeId) + 0x9e3779b97f4a7c15ULL);
        value ^= (static_cast<std::uint64_t>(hopIndex) + 0xbf58476d1ce4e5b9ULL);
        value ^= (salt + 0x94d049bb133111ebULL);
        value ^= static_cast<std::uint64_t>(m_seed) << 1U;
        value ^= value >> 30U;
        value *= 0xbf58476d1ce4e5b9ULL;
        value ^= value >> 27U;
        value *= 0x94d049bb133111ebULL;
        value ^= value >> 31U;
        return value;
    }

    double Sample(std::uint64_t salt, double minValue, double maxValue) const
    {
        if (maxValue <= minValue)
        {
            return minValue;
        }

        std::mt19937_64 rng(salt);
        std::uniform_real_distribution<double> distribution(minValue, maxValue);
        return distribution(rng);
    }

    double m_benignMin{0.0};
    double m_benignMax{0.0};
    double m_maliciousMin{0.0};
    double m_maliciousMax{0.0};
    std::set<NodeId> m_maliciousNodes;
    std::uint32_t m_seed{1};
    double m_propagationDelay{0.01};
};

class RoutePolicy
{
  public:
    virtual ~RoutePolicy() = default;
    virtual std::string Name() const = 0;
    virtual datamut::RoutePlan BuildRoute(const datamut::TimeWindowGraph& graph,
                                          NodeId source,
                                          NodeId sink,
                                          double startTime) = 0;
};

class AodvPolicy final : public RoutePolicy
{
  public:
    std::string Name() const override
    {
        return "AODV";
    }

    datamut::RoutePlan BuildRoute(const datamut::TimeWindowGraph& graph,
                                  NodeId source,
                                  NodeId sink,
                                  double startTime) override
    {
        return graph.ComputeExpectedRoute(source, sink, startTime);
    }
};

class CachedRoutePolicy : public RoutePolicy
{
  public:
    CachedRoutePolicy(std::string name, double refreshPeriodSeconds, bool cacheForever)
        : m_name(std::move(name)), m_refreshPeriodSeconds(refreshPeriodSeconds), m_cacheForever(cacheForever)
    {
    }

    std::string Name() const override
    {
        return m_name;
    }

    datamut::RoutePlan BuildRoute(const datamut::TimeWindowGraph& graph,
                                  NodeId source,
                                  NodeId sink,
                                  double startTime) override
    {
        const auto key = std::make_pair(source, sink);
        auto& entry = m_cache[key];

        const bool needsRefresh = !entry.valid || (!m_cacheForever && startTime >= entry.refreshDeadline) ||
                                  (entry.valid && !entry.prototype.reachable);
        if (needsRefresh)
        {
            entry.prototype = graph.ComputeExpectedRoute(source, sink, startTime);
            entry.valid = true;
            entry.refreshDeadline = startTime + m_refreshPeriodSeconds;
        }

        if (!entry.valid)
        {
            return {};
        }

        return ReplayRoutePlan(graph, entry.prototype, startTime);
    }

  private:
    struct CacheEntry
    {
        datamut::RoutePlan prototype;
        double refreshDeadline{0.0};
        bool valid{false};
    };

    std::string m_name;
    double m_refreshPeriodSeconds{0.0};
    bool m_cacheForever{false};
    std::map<std::pair<NodeId, NodeId>, CacheEntry> m_cache;
};

class OlsrPolicy final : public CachedRoutePolicy
{
  public:
    explicit OlsrPolicy(double refreshPeriodSeconds)
        : CachedRoutePolicy("OLSR", refreshPeriodSeconds, false)
    {
    }
};

class DsrPolicy final : public CachedRoutePolicy
{
  public:
    DsrPolicy()
        : CachedRoutePolicy("DSR", 1e9, true)
    {
    }
};

class DsdvPolicy final : public CachedRoutePolicy
{
  public:
    explicit DsdvPolicy(double refreshPeriodSeconds)
        : CachedRoutePolicy("DSDV", refreshPeriodSeconds, false)
    {
    }
};

struct PacketScore
{
    bool flagged{false};
    std::uint32_t deviatingHops{0};
    std::uint32_t packetsSeen{0};
};

class PaperExactDetector
{
  public:
    PaperExactDetector(std::string policyName, double deviationEpsilonSeconds)
        : m_policyName(std::move(policyName)), m_deviationEpsilonSeconds(deviationEpsilonSeconds)
    {
    }

    void ObservePacket(RoutePolicy& policy,
                       const datamut::TimeWindowGraph& graph,
                       const datamut::RoutePlan& expectedPlan,
                       const datamut::PacketLogger& logger,
                       PacketId packetId)
    {
        const auto& hops = logger.HopsForPacket(packetId);
        if (hops.empty() || !expectedPlan.reachable || expectedPlan.steps.size() < 2)
        {
            return;
        }

        std::vector<NodeId> observedPath;
        observedPath.push_back(expectedPlan.steps.front().node);
        for (const auto& hop : hops)
        {
            observedPath.push_back(hop.nextHop);
        }

        std::cout << "[" << m_policyName << "] packet " << packetId << '\n';
        std::cout << "  expected path: " << graph.PathToString(expectedPlan) << '\n';
        std::cout << "  observed path: " << graph.PathToString(observedPath) << '\n';

        double currentTime = expectedPlan.steps.front().arrivalTime;
        const NodeId sink = expectedPlan.steps.back().node;

        for (std::size_t hopIndex = 0; hopIndex < hops.size(); ++hopIndex)
        {
            const auto& hop = hops[hopIndex];
            const datamut::EncounterWindow* window = graph.FindWindow(hop.encounterWindowId);
            if (window == nullptr)
            {
                continue;
            }

            const double expectedSendTime = graph.NextContactTime(currentTime, *window);
            const double residualDelay = hop.sendTime - expectedSendTime;
            const datamut::RoutePlan localExpectedPlan = policy.BuildRoute(graph, hop.from, sink, currentTime);
            const NodeId localNextHop = (localExpectedPlan.reachable && localExpectedPlan.steps.size() >= 2)
                                            ? localExpectedPlan.steps[1].node
                                            : -1;
            const bool pathMatch = localNextHop == hop.nextHop;
            const bool delayMatch = residualDelay <= m_deviationEpsilonSeconds;
            const bool hopSuspicious = !pathMatch || !delayMatch;

            std::cout << "    hop " << hopIndex << ": " << graph.NodeLabel(hop.from) << " -> "
                      << graph.NodeLabel(hop.nextHop) << " | intended_send=" << std::fixed << std::setprecision(3)
                      << expectedSendTime << " local_next=" << graph.NodeLabel(localNextHop)
                      << " observed=" << hop.sendTime << " residual=" << residualDelay
                      << " epsilon=" << m_deviationEpsilonSeconds << " pathMatch=" << (pathMatch ? "yes" : "no")
                      << " suspicious=" << (hopSuspicious ? "yes" : "no") << '\n';
            std::cout << "      sender " << graph.NodeLabel(hop.from) << " intended to forward at "
                      << std::fixed << std::setprecision(3) << expectedSendTime << " to "
                      << graph.NodeLabel(hop.nextHop) << '\n';

            auto& score = m_scores[hop.from];
            score.packetsSeen += 1;
            if (hopSuspicious)
            {
                score.deviatingHops += 1;
                score.flagged = true;
            }

            currentTime = hop.receiveTime;
        }
    }

    void PrintReport(const datamut::TimeWindowGraph& graph) const
    {
        std::cout << "\n=== " << m_policyName << " paper-accurate malicious node report ===\n";
        for (const auto& [nodeId, score] : m_scores)
        {
            std::cout << graph.NodeLabel(nodeId)
                      << " packetsSeen=" << score.packetsSeen
                      << " deviatingHops=" << score.deviatingHops
                      << " flagged=" << (score.flagged ? "yes" : "no") << '\n';
        }

        if (m_scores.empty())
        {
            std::cout << "No suspicious nodes detected." << std::endl;
        }
    }

    std::vector<NodeId> SuspectedNodes() const
    {
        std::vector<NodeId> result;
        for (const auto& [nodeId, score] : m_scores)
        {
            if (score.flagged)
            {
                result.push_back(nodeId);
            }
        }
        return result;
    }

  private:
    std::string m_policyName;
    double m_deviationEpsilonSeconds{0.25};
    std::map<NodeId, PacketScore> m_scores;
};

struct PolicyBundle
{
    std::unique_ptr<RoutePolicy> policy;
    std::string reportFileBase;
};

struct MetricsSnapshot
{
    int tp{0};
    int fp{0};
    int fn{0};
    int tn{0};
    double precision{0.0};
    double recall{0.0};
    double f1{0.0};
    double fpr{0.0};
};

struct StatsAccumulator
{
    int count{0};
    double sum{0.0};
    double sumSquares{0.0};

    void Add(double value)
    {
        count += 1;
        sum += value;
        sumSquares += value * value;
    }

    double Mean() const
    {
        return count == 0 ? 0.0 : sum / static_cast<double>(count);
    }

    double Stddev() const
    {
        if (count < 2)
        {
            return 0.0;
        }

        const double mean = Mean();
        const double variance = (sumSquares / static_cast<double>(count)) - mean * mean;
        return variance > 0.0 ? std::sqrt(variance) : 0.0;
    }
};

struct ProtocolAggregate
{
    StatsAccumulator tp;
    StatsAccumulator fp;
    StatsAccumulator fn;
    StatsAccumulator tn;
    StatsAccumulator precision;
    StatsAccumulator recall;
    StatsAccumulator f1;
    StatsAccumulator fpr;
    StatsAccumulator executionTimeMs;

    void Add(const MetricsSnapshot& snapshot)
    {
        tp.Add(static_cast<double>(snapshot.tp));
        fp.Add(static_cast<double>(snapshot.fp));
        fn.Add(static_cast<double>(snapshot.fn));
        tn.Add(static_cast<double>(snapshot.tn));
        precision.Add(snapshot.precision);
        recall.Add(snapshot.recall);
        f1.Add(snapshot.f1);
        fpr.Add(snapshot.fpr);
    }

    void AddExecutionTimeMs(double value)
    {
        executionTimeMs.Add(value);
    }
};

class ExperimentRunner
{
  public:
    struct ScenarioConfig
    {
        datamut::TimeWindowGraph graph;
        std::vector<NodeId> sources;
        std::vector<double> startTimes;
        NodeId sink{16};
        std::string topologyTag;
        std::set<NodeId> maliciousNodes;
    };

    int Run()
    {
        const int scenarioId = ReadEnvInt("DATAMUT_SCENARIO", 1, 1);
        const ScenarioConfig scenario = BuildScenario(scenarioId);

        const datamut::TimeWindowGraph& graph = scenario.graph;
        const std::vector<NodeId>& sources = scenario.sources;
        const std::vector<double>& startTimes = scenario.startTimes;
        const NodeId sink = scenario.sink;
        const std::string topologyTag = scenario.topologyTag;
        const std::set<NodeId>& maliciousNodes = scenario.maliciousNodes;
        const double deviationEpsilonSeconds = 0.25;
        const int seedBase = ReadEnvInt("DATAMUT_SEED_BASE", 37, 0);
        const int seedCount = ReadEnvInt("DATAMUT_NUM_SEEDS", 10, 1);
        const bool hasSingleSeedOverride = std::getenv("DATAMUT_SEED") != nullptr;
        const int singleSeed = ReadEnvInt("DATAMUT_SEED", seedBase, 0);

        const int effectiveSeedBase = hasSingleSeedOverride ? singleSeed : seedBase;
        const int effectiveSeedCount = hasSingleSeedOverride ? 1 : seedCount;
        std::map<std::string, ProtocolAggregate> protocolAggregates;

        std::cout << "=== DATAMUt paper-style packet-by-packet demo ===\n";
        std::cout << "Scenario: " << scenarioId << "\n";
        std::cout << "Topology: " << topologyTag << "\n\n";

        std::cout << "Seed configuration: base=" << effectiveSeedBase
                  << " count=" << effectiveSeedCount << "\n\n";

        for (int seedOffset = 0; seedOffset < effectiveSeedCount; ++seedOffset)
        {
            const int seed = effectiveSeedBase + seedOffset;
            const DelayModel attackModel(0.05,
                                         0.18,
                                         1.00,
                                         7.00,
                                         maliciousNodes,
                                         static_cast<std::uint32_t>(seed),
                                         0.02);

            std::vector<PolicyBundle> bundles;
            bundles.push_back({std::make_unique<AodvPolicy>(), "datamut-paper-analysis-AODV.csv"});
            bundles.push_back({std::make_unique<OlsrPolicy>(12.0), "datamut-paper-analysis-OLSR.csv"});
            bundles.push_back({std::make_unique<DsrPolicy>(), "datamut-paper-analysis-DSR.csv"});
            bundles.push_back({std::make_unique<DsdvPolicy>(18.0), "datamut-paper-analysis-DSDV.csv"});

            std::cout << "--- running seed " << seed << " ---\n";
            for (auto& bundle : bundles)
            {
                const auto policyStart = std::chrono::steady_clock::now();
                const MetricsSnapshot snapshot = RunDetection(*bundle.policy,
                                                              graph,
                                                              sources,
                                                              startTimes,
                                                              sink,
                                                              attackModel,
                                                              deviationEpsilonSeconds,
                                                              AppendSeedToReportName(bundle.reportFileBase, seed),
                                                              seed,
                                                              maliciousNodes);
                const auto policyEnd = std::chrono::steady_clock::now();
                const double elapsedMs = std::chrono::duration<double, std::milli>(policyEnd - policyStart).count();
                protocolAggregates[bundle.policy->Name()].AddExecutionTimeMs(elapsedMs);
                protocolAggregates[bundle.policy->Name()].Add(snapshot);
            }
            std::cout << '\n';
        }

        WriteProtocolMetricsSummary("datamut-paper-metrics-by-protocol.csv", protocolAggregates);
        PrintExecutionTimeSummary(protocolAggregates);

        return 0;
    }

  private:
    static int ReadEnvInt(const char* name, int fallback, int minValue)
    {
        const char* rawValue = std::getenv(name);
        if (rawValue == nullptr)
        {
            return fallback;
        }

        char* parseEnd = nullptr;
        const long parsed = std::strtol(rawValue, &parseEnd, 10);
        if (parseEnd == rawValue || *parseEnd != '\0' || parsed < static_cast<long>(minValue))
        {
            return fallback;
        }

        return static_cast<int>(parsed);
    }

    static ScenarioConfig BuildScenario(int scenarioId)
    {
        if (scenarioId == 3)
        {
            return BuildDoubleRingScenario();
        }

        if (scenarioId == 2)
        {
            return BuildRingScenario();
        }

        return BuildGridScenario();
    }

    static std::string AppendSeedToReportName(const std::string& fileName, int seed)
    {
        const std::string seedSuffix = "-seed" + std::to_string(seed);
        const std::size_t dotPos = fileName.rfind('.');
        if (dotPos == std::string::npos)
        {
            return fileName + seedSuffix;
        }

        return fileName.substr(0, dotPos) + seedSuffix + fileName.substr(dotPos);
    }

    static std::string JoinNodeLabels(const datamut::TimeWindowGraph& graph, const std::set<NodeId>& nodes)
    {
        std::ostringstream out;
        bool first = true;
        for (NodeId nodeId : nodes)
        {
            if (!first)
            {
                out << ';';
            }
            out << graph.NodeLabel(nodeId);
            first = false;
        }
        return out.str();
    }

    static std::set<NodeId> ToNodeSet(const std::vector<NodeId>& nodes)
    {
        return std::set<NodeId>(nodes.begin(), nodes.end());
    }

    static double SafeRatio(int numerator, int denominator)
    {
        return denominator == 0 ? 0.0 : static_cast<double>(numerator) / static_cast<double>(denominator);
    }

    static void AppendMetricsSummary(const std::string& metricsFile,
                                     const datamut::TimeWindowGraph& graph,
                                     const std::string& policyName,
                                     int seed,
                                     NodeId sink,
                                     const std::set<NodeId>& maliciousNodes,
                                     const std::set<NodeId>& suspectedNodes,
                                     MetricsSnapshot* snapshotOut)
    {
        const bool fileExists = static_cast<bool>(std::ifstream(metricsFile));
        std::ofstream out(metricsFile, std::ios::app);
        if (!out.is_open())
        {
            return;
        }

        if (!fileExists)
        {
            out << "seed,policy,malicious_nodes,suspected_nodes,tp,fp,fn,tn,precision,recall,f1,fpr" << '\n';
        }

        int tp = 0;
        int fp = 0;
        int fn = 0;
        int tn = 0;

        for (NodeId nodeId = 0; nodeId < sink; ++nodeId)
        {
            const bool isMalicious = maliciousNodes.find(nodeId) != maliciousNodes.end();
            const bool isSuspected = suspectedNodes.find(nodeId) != suspectedNodes.end();

            if (isMalicious && isSuspected)
            {
                tp += 1;
            }
            else if (!isMalicious && isSuspected)
            {
                fp += 1;
            }
            else if (isMalicious && !isSuspected)
            {
                fn += 1;
            }
            else
            {
                tn += 1;
            }
        }

        const double precision = SafeRatio(tp, tp + fp);
        const double recall = SafeRatio(tp, tp + fn);
        const double f1 = (precision + recall) > 0.0 ? (2.0 * precision * recall) / (precision + recall) : 0.0;
        const double fpr = SafeRatio(fp, fp + tn);

        if (snapshotOut != nullptr)
        {
            snapshotOut->tp = tp;
            snapshotOut->fp = fp;
            snapshotOut->fn = fn;
            snapshotOut->tn = tn;
            snapshotOut->precision = precision;
            snapshotOut->recall = recall;
            snapshotOut->f1 = f1;
            snapshotOut->fpr = fpr;
        }

        out << seed << ',' << policyName << ',' << JoinNodeLabels(graph, maliciousNodes) << ','
            << JoinNodeLabels(graph, suspectedNodes) << ',' << tp << ',' << fp << ',' << fn << ',' << tn << ','
            << std::fixed << std::setprecision(6) << precision << ',' << recall << ',' << f1 << ',' << fpr << '\n';
    }

    static void WriteProtocolMetricsSummary(const std::string& fileName,
                                            const std::map<std::string, ProtocolAggregate>& aggregates)
    {
        std::ofstream out(fileName, std::ios::out);
        if (!out.is_open())
        {
            return;
        }

        out << "policy,runs,tp_mean,tp_std,fp_mean,fp_std,fn_mean,fn_std,tn_mean,tn_std,"
               "precision_mean,precision_std,recall_mean,recall_std,f1_mean,f1_std,fpr_mean,fpr_std,"
               "execution_time_ms_mean,execution_time_ms_std"
            << '\n';

        for (const auto& [policyName, agg] : aggregates)
        {
            out << policyName << ',' << agg.precision.count << ',' << std::fixed << std::setprecision(6)
                << agg.tp.Mean() << ',' << agg.tp.Stddev() << ',' << agg.fp.Mean() << ',' << agg.fp.Stddev() << ','
                << agg.fn.Mean() << ',' << agg.fn.Stddev() << ',' << agg.tn.Mean() << ',' << agg.tn.Stddev() << ','
                << agg.precision.Mean() << ',' << agg.precision.Stddev() << ',' << agg.recall.Mean() << ','
                << agg.recall.Stddev() << ',' << agg.f1.Mean() << ',' << agg.f1.Stddev() << ',' << agg.fpr.Mean()
                << ',' << agg.fpr.Stddev() << ',' << agg.executionTimeMs.Mean() << ','
                << agg.executionTimeMs.Stddev() << '\n';
        }
    }

    static void PrintExecutionTimeSummary(const std::map<std::string, ProtocolAggregate>& aggregates)
    {
        std::cout << "=== Average execution time by routing algorithm ===\n";
        for (const auto& [policyName, agg] : aggregates)
        {
            std::cout << policyName << ": mean=" << std::fixed << std::setprecision(3) << agg.executionTimeMs.Mean()
                      << " ms, stddev=" << agg.executionTimeMs.Stddev() << " ms over "
                      << agg.executionTimeMs.count << " seeds\n";
        }
    }

    static ScenarioConfig BuildGridScenario()
    {
        ScenarioConfig scenario;
        scenario.sink = 16;
        scenario.topologyTag = "grid4x4-temporal";
        scenario.sources = {1};   // N2
        scenario.startTimes = {11.0};
        scenario.maliciousNodes = {5,9}; // N6, N10

        datamut::TimeWindowGraph graph(60.0);
        graph.SetSinkNode(scenario.sink);
        graph.AddWindow(1, 0, 1, 0.0, 5.0);
        graph.AddWindow(2, 1, 2, 30.0, 35.0);
        graph.AddWindow(3, 2, 3, 0.0, 5.0);
        graph.AddWindow(4, 4, 5, 30.0, 35.0);
        graph.AddWindow(5, 5, 6, 0.0, 5.0);
        graph.AddWindow(6, 6, 7, 30.0, 35.0);
        graph.AddWindow(7, 8, 9, 0.0, 5.0);
        graph.AddWindow(8, 9, 10, 30.0, 35.0);
        graph.AddWindow(9, 10, 11, 0.0, 5.0);
        graph.AddWindow(10, 12, 13, 30.0, 35.0);
        graph.AddWindow(11, 13, 14, 0.0, 5.0);
        graph.AddWindow(12, 14, 15, 30.0, 35.0);
        graph.AddWindow(13, 0, 4, 15.0, 20.0);
        graph.AddWindow(14, 1, 5, 45.0, 50.0);
        graph.AddWindow(15, 2, 6, 15.0, 20.0);
        graph.AddWindow(16, 3, 7, 45.0, 50.0);
        graph.AddWindow(17, 4, 8, 45.0, 50.0);
        graph.AddWindow(18, 5, 9, 15.0, 20.0);
        graph.AddWindow(19, 6, 10, 45.0, 50.0);
        graph.AddWindow(20, 7, 11, 15.0, 20.0);
        graph.AddWindow(21, 8, 12, 15.0, 20.0);
        graph.AddWindow(22, 9, 13, 45.0, 50.0);
        graph.AddWindow(23, 10, 14, 15.0, 20.0);
        graph.AddWindow(24, 11, 15, 45.0, 50.0);
        graph.AddWindow(25, 12, 16, 40.0, 55.0);
        graph.AddWindow(26, 13, 16, 10.0, 25.0);
        graph.AddWindow(27, 14, 16, 40.0, 55.0);
        graph.AddWindow(28, 15, 16, 10.0, 25.0);
        scenario.graph = std::move(graph);
        return scenario;
    }

    static ScenarioConfig BuildRingScenario()
    {
        ScenarioConfig scenario;
        scenario.sink = 9;
        scenario.topologyTag = "ring9plus-sink-temporal";
        scenario.sources = {4};   // N5
        scenario.startTimes = {11.0};
        scenario.maliciousNodes = {3,2};  //N4,N3

        datamut::TimeWindowGraph graph(60.0);
        graph.SetSinkNode(scenario.sink);

        // Ring-like structure: n1-n2-...-n9, with sink linked only to n1 and n9.
        graph.AddWindow(1, 0, 1, 15.0, 20.0); // n1 <-> n2
        graph.AddWindow(2, 0, 9, 44.0, 59.0); // n1 <-> S
        graph.AddWindow(3, 1, 2, 0.0, 5.0); // n2 <-> n3
        graph.AddWindow(4, 2, 3, 30.0, 35.0); // n3 <-> n4
        graph.AddWindow(5, 3, 4, 5.0, 10.0); // n4 <-> n5
        graph.AddWindow(6, 4, 5, 43.0, 48.0); // n5 <-> n6
        graph.AddWindow(7, 5, 6, 17.0, 22.0); // n6 <-> n7
        graph.AddWindow(8, 6, 7, 53.0, 58.0); // n7 <-> n8
        graph.AddWindow(9, 7, 8, 30.0, 35.0); // n8 <-> n9
        graph.AddWindow(10, 8, 9, 0.0, 15.0); // n9 <-> S

        scenario.graph = std::move(graph);
        return scenario;
    }

    static ScenarioConfig BuildDoubleRingScenario()
    {
        ScenarioConfig scenario;
        scenario.sink = 15;
        scenario.topologyTag = "double-ring-temporal";
        scenario.sources = {0};   // N1
        scenario.startTimes = {11.0};
        scenario.maliciousNodes = {4,2}; // N5, N3

        datamut::TimeWindowGraph graph(60.0);
        graph.SetSinkNode(scenario.sink);

        // Left ring: n1-n2-n4-n6-n8-n7-n5-n3-n1
        graph.AddWindow(1, 0, 1, 5.0, 10.0);
        graph.AddWindow(2, 1, 3, 42.0, 47.0);
        graph.AddWindow(3, 3, 5, 13.0, 18.0);
        graph.AddWindow(4, 5, 7, 48.0, 53.0);
        graph.AddWindow(5, 0, 2, 20.0, 25.0);
        graph.AddWindow(6, 2, 4, 43.0, 48.0);
        graph.AddWindow(7, 4, 6, 13.0, 18.0);
        graph.AddWindow(8, 6, 7, 35.0, 40.0);

        // Right ring: n8-n10-n12-n14-n15-n13-n11-n9-n8, sink attached to n15
        graph.AddWindow(9, 7, 9, 5.0, 10.0);
        graph.AddWindow(10, 9, 11, 42.0, 47.0);
        graph.AddWindow(11, 11, 13, 13.0, 18.0);
        graph.AddWindow(12, 13, 14, 48.0, 53.0);
        graph.AddWindow(13, 14, 15, 5.0, 20.0);
        graph.AddWindow(14, 7, 8, 20.0, 25.0);
        graph.AddWindow(15, 8, 10, 42.0, 47.0);
        graph.AddWindow(16, 10, 12, 43.0, 48.0);
        graph.AddWindow(17, 12, 14, 35.0, 40.0);

        scenario.graph = std::move(graph);
        return scenario;
    }

    static PacketOutcome SimulatePacket(const datamut::TimeWindowGraph& graph,
                                        RoutePolicy& policy,
                                        NodeId source,
                                        NodeId sink,
                                        PacketId packetId,
                                        double startTime,
                                        const DelayModel& delayModel)
    {
        PacketOutcome outcome;
        outcome.route.reachable = true;
        outcome.route.totalArrivalTime = startTime;
        outcome.route.steps.push_back({source, startTime, -1});

        double currentTime = startTime;
        NodeId currentNode = source;
        const std::size_t maxHopCount = 64;

        for (std::size_t hopIndex = 0; hopIndex < maxHopCount && currentNode != sink; ++hopIndex)
        {
            const datamut::RoutePlan remainingRoute = policy.BuildRoute(graph, currentNode, sink, currentTime);
            if (!remainingRoute.reachable || remainingRoute.steps.size() < 2)
            {
                outcome.route.reachable = false;
                break;
            }

            const auto& fromStep = remainingRoute.steps.front();
            const auto& toStep = remainingRoute.steps[1];
            const datamut::EncounterWindow* window = graph.FindWindow(toStep.encounterWindowId);
            if (window == nullptr)
            {
                outcome.route.reachable = false;
                break;
            }

            const double expectedSendTime = graph.NextContactTime(currentTime, *window);
            const double benignDelay = delayModel.BenignDelay(fromStep.node, packetId, hopIndex);
            const double maliciousDelay = delayModel.MaliciousExtraDelay(fromStep.node, packetId, hopIndex);
            const double totalDelay = benignDelay + maliciousDelay;
            const double sendTime = expectedSendTime + totalDelay;

            double phase = std::fmod(currentTime, graph.PeriodSeconds());
            if (phase < 0.0)
            {
                phase += graph.PeriodSeconds();
            }
            const double cycleStart = currentTime - phase;
            double windowStartAbsolute = cycleStart + window->start;
            double windowEndAbsolute = cycleStart + window->end;

            if (phase > window->end + 1e-9)
            {
                windowStartAbsolute += graph.PeriodSeconds();
                windowEndAbsolute += graph.PeriodSeconds();
            }
            else if (phase < window->start - 1e-9)
            {
                // already set for the current cycle
            }

            if (sendTime > windowEndAbsolute + 1e-9)
            {
                std::ostringstream missed;
                missed << "packet " << packetId << " missed opportunity: " << graph.NodeLabel(fromStep.node)
                       << " -> " << graph.NodeLabel(toStep.node) << " window=" << toStep.encounterWindowId
                       << " expected=" << std::fixed << std::setprecision(3) << expectedSendTime
                       << " send=" << sendTime << " windowStart=" << windowStartAbsolute
                       << " windowEnd=" << windowEndAbsolute;
                outcome.missedOpportunities.push_back(missed.str());
                currentTime = sendTime;
                continue;
            }

            const double receiveTime = sendTime + delayModel.PropagationDelay();

            outcome.logger.RecordHop({packetId,
                                      fromStep.node,
                                      toStep.node,
                                      sendTime,
                                      receiveTime,
                                      toStep.encounterWindowId});

            outcome.route.steps.push_back({toStep.node, receiveTime, toStep.encounterWindowId});
            currentNode = toStep.node;
            currentTime = receiveTime;
        }

        if (currentNode != sink)
        {
            outcome.route.reachable = false;
        }

        outcome.route.totalArrivalTime = currentTime;
        return outcome;
    }

    static MetricsSnapshot RunDetection(RoutePolicy& policy,
                                        const datamut::TimeWindowGraph& graph,
                                        const std::vector<NodeId>& sources,
                                        const std::vector<double>& startTimes,
                                        NodeId sink,
                                        const DelayModel& attackModel,
                                        double deviationEpsilonSeconds,
                                        const std::string& reportFile,
                                        int seed,
                                        const std::set<NodeId>& maliciousNodes)
    {
        MetricsSnapshot snapshot;
        PaperExactDetector detector(policy.Name(), deviationEpsilonSeconds);
        PacketId packetId = 1001;

        for (NodeId source : sources)
        {
            for (double startTime : startTimes)
            {
                const datamut::RoutePlan expectedPlan = policy.BuildRoute(graph, source, sink, startTime);
                const PacketOutcome packet = SimulatePacket(graph,
                                                            policy,
                                                            source,
                                                            sink,
                                                            packetId,
                                                            startTime,
                                                            attackModel);
                for (const auto& missed : packet.missedOpportunities)
                {
                    std::cout << "  " << missed << '\n';
                }
                detector.ObservePacket(policy, graph, expectedPlan, packet.logger, packetId);
                ++packetId;
            }
        }

        detector.PrintReport(graph);

        std::ofstream reportOut(reportFile, std::ios::out);
        reportOut << "policy,suspected_nodes" << '\n';
        reportOut << policy.Name() << ',';
        const auto suspected = detector.SuspectedNodes();
        for (std::size_t i = 0; i < suspected.size(); ++i)
        {
            if (i > 0)
            {
                reportOut << ';';
            }
            reportOut << graph.NodeLabel(suspected[i]);
        }
        reportOut << '\n';

        AppendMetricsSummary("datamut-paper-metrics-summary.csv",
                             graph,
                             policy.Name(),
                             seed,
                             sink,
                             maliciousNodes,
                             ToNodeSet(suspected),
                             &snapshot);

        std::cout << "[" << policy.Name() << "] paper-style report -> " << reportFile << '\n';
        return snapshot;
    }
};

} // namespace

int
main()
{
    ExperimentRunner runner;
    return runner.Run();
}
