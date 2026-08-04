#ifndef DATAMUT_ANALYSIS_H
#define DATAMUT_ANALYSIS_H

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <functional>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <map>
#include <queue>
#include <sstream>
#include <string>
#include <utility>
#include <vector>

namespace datamut
{

using NodeId = int;
using PacketId = std::uint64_t;

struct EncounterWindow
{
    int id{-1};
    NodeId a{-1};
    NodeId b{-1};
    double start{0.0};
    double end{0.0};
};

struct HopLogEntry
{
    PacketId packetId{0};
    NodeId from{-1};
    NodeId nextHop{-1};
    double sendTime{0.0};
    double receiveTime{0.0};
    int encounterWindowId{-1};
};

struct RouteStep
{
    NodeId node{-1};
    double arrivalTime{0.0};
    int encounterWindowId{-1};
};

struct RoutePlan
{
    bool reachable{false};
    double totalArrivalTime{std::numeric_limits<double>::infinity()};
    std::vector<RouteStep> steps;
};

struct NodeScore
{
    double residualSum{0.0};
    std::uint32_t samples{0};
    std::uint32_t breaches{0};
    bool flagged{false};
};

struct ResidualSummary
{
    double sum{0.0};
    double sumSquares{0.0};
    std::uint32_t samples{0};

    void Add(double residual)
    {
        sum += residual;
        sumSquares += residual * residual;
        samples += 1;
    }

    double Mean() const
    {
        return samples == 0 ? 0.0 : sum / static_cast<double>(samples);
    }

    double Stddev() const
    {
        if (samples < 2)
        {
            return 0.0;
        }

        const double mean = Mean();
        const double variance = (sumSquares / static_cast<double>(samples)) - (mean * mean);
        return variance > 0.0 ? std::sqrt(variance) : 0.0;
    }
};

class ThresholdModel
{
  public:
    void SetDefaultThreshold(double thresholdSeconds)
    {
        m_defaultThresholdSeconds = thresholdSeconds;
    }

    void SetThreshold(NodeId nodeId, double thresholdSeconds)
    {
        m_thresholdByNode[nodeId] = thresholdSeconds;
    }

    double ThresholdFor(NodeId nodeId) const
    {
        const auto it = m_thresholdByNode.find(nodeId);
        return it == m_thresholdByNode.end() ? m_defaultThresholdSeconds : it->second;
    }

    bool Empty() const
    {
        return m_thresholdByNode.empty();
    }

    bool WriteCsv(const std::string& fileName,
                  const std::string& protocolName,
                  const std::string& topologyTag,
                  const std::map<NodeId, ResidualSummary>& summaries,
                  double sigmaMultiplier,
                  double minimumThresholdSeconds) const
    {
        std::ofstream out(fileName, std::ios::out);
        if (!out.is_open())
        {
            return false;
        }

        out << "protocol,topology,node_id,samples,mean_residual,stddev_residual,threshold_seconds" << '\n';
        for (const auto& [nodeId, summary] : summaries)
        {
            const double thresholdSeconds = std::max(minimumThresholdSeconds,
                                                     summary.Mean() + sigmaMultiplier * summary.Stddev());
            out << protocolName << ',' << topologyTag << ',' << nodeId << ',' << summary.samples << ','
                << std::fixed << std::setprecision(6) << summary.Mean() << ',' << summary.Stddev() << ','
                << thresholdSeconds << '\n';
        }

        return true;
    }

    bool LoadCsv(const std::string& fileName,
                 const std::string& protocolName,
                 const std::string& topologyTag)
    {
        std::ifstream in(fileName);
        if (!in.is_open())
        {
            return false;
        }

        m_thresholdByNode.clear();
        m_defaultThresholdSeconds = 0.0;

        std::string line;
        bool sawRow = false;
        while (std::getline(in, line))
        {
            if (line.empty() || line.rfind("protocol,", 0) == 0)
            {
                continue;
            }

            std::stringstream ss(line);
            std::string protocolField;
            std::string topologyField;
            std::string nodeField;
            std::string samplesField;
            std::string meanField;
            std::string stddevField;
            std::string thresholdField;

            if (!std::getline(ss, protocolField, ',') || !std::getline(ss, topologyField, ',') ||
                !std::getline(ss, nodeField, ',') || !std::getline(ss, samplesField, ',') ||
                !std::getline(ss, meanField, ',') || !std::getline(ss, stddevField, ',') ||
                !std::getline(ss, thresholdField, ','))
            {
                continue;
            }

            if (protocolField != protocolName || topologyField != topologyTag)
            {
                continue;
            }

            const NodeId nodeId = static_cast<NodeId>(std::stoi(nodeField));
            const double thresholdSeconds = std::stod(thresholdField);
            m_thresholdByNode[nodeId] = thresholdSeconds;
            sawRow = true;
        }

        if (sawRow)
        {
            m_defaultThresholdSeconds = m_thresholdByNode.begin()->second;
        }

        return sawRow;
    }

  private:
    double m_defaultThresholdSeconds{1.0};
    std::map<NodeId, double> m_thresholdByNode;
};

class ThresholdCalibrator
{
  public:
    void AddResidual(NodeId nodeId, double residualSeconds)
    {
        m_summaries[nodeId].Add(residualSeconds);
    }

    bool Empty() const
    {
        return m_summaries.empty();
    }

    ThresholdModel BuildModel(double sigmaMultiplier, double minimumThresholdSeconds) const
    {
        ThresholdModel model;
        model.SetDefaultThreshold(minimumThresholdSeconds);
        for (const auto& [nodeId, summary] : m_summaries)
        {
            const double thresholdSeconds = std::max(minimumThresholdSeconds,
                                                     summary.Mean() + sigmaMultiplier * summary.Stddev());
            model.SetThreshold(nodeId, thresholdSeconds);
        }
        return model;
    }

    bool WriteCsv(const std::string& fileName,
                  const std::string& protocolName,
                  const std::string& topologyTag,
                  double sigmaMultiplier,
                  double minimumThresholdSeconds) const
    {
        ThresholdModel model;
        return model.WriteCsv(fileName,
                              protocolName,
                              topologyTag,
                              m_summaries,
                              sigmaMultiplier,
                              minimumThresholdSeconds);
    }

  private:
    std::map<NodeId, ResidualSummary> m_summaries;
};

class PacketLogger
{
  public:
    void RecordHop(const HopLogEntry& entry)
    {
        m_hopsByPacket[entry.packetId].push_back(entry);
    }

    const std::vector<HopLogEntry>& HopsForPacket(PacketId packetId) const
    {
        static const std::vector<HopLogEntry> empty;
        const auto it = m_hopsByPacket.find(packetId);
        return it == m_hopsByPacket.end() ? empty : it->second;
    }

  private:
    std::map<PacketId, std::vector<HopLogEntry>> m_hopsByPacket;
};

class TimeWindowGraph
{
  public:
    explicit TimeWindowGraph(double periodSeconds = 60.0)
        : m_periodSeconds(periodSeconds)
    {
    }

    void AddWindow(int id, NodeId a, NodeId b, double start, double end)
    {
        m_windows.push_back({id, a, b, start, end});
        m_windowById[id] = {id, a, b, start, end};
        m_maxNodeId = std::max(m_maxNodeId, std::max(a, b));
    }

    void SetSinkNode(NodeId sinkNode)
    {
        m_sinkNode = sinkNode;
    }

    const EncounterWindow* FindWindow(int id) const
    {
        const auto it = m_windowById.find(id);
        return it == m_windowById.end() ? nullptr : &it->second;
    }

    double NextContactTime(double now, const EncounterWindow& window) const
    {
        double phase = std::fmod(now, m_periodSeconds);
        if (phase < 0.0)
        {
            phase += m_periodSeconds;
        }

        if (phase < window.start)
        {
            return now + (window.start - phase);
        }
        if (phase <= window.end)
        {
            return now;
        }
        return now + (m_periodSeconds - phase) + window.start;
    }

    double PeriodSeconds() const
    {
        return m_periodSeconds;
    }

    RoutePlan ComputeExpectedRoute(NodeId source, NodeId sink, double startTime) const
    {
        RoutePlan plan;
        const int nodeCount = std::max(m_maxNodeId, std::max(source, sink)) + 1;
        if (nodeCount <= 0)
        {
            return plan;
        }

        std::vector<double> bestArrival(nodeCount, std::numeric_limits<double>::infinity());
        std::vector<NodeId> parent(nodeCount, -1);
        std::vector<int> parentWindowId(nodeCount, -1);

        using QueueItem = std::pair<double, NodeId>;
        std::priority_queue<QueueItem, std::vector<QueueItem>, std::greater<QueueItem>> pq;
        bestArrival[source] = startTime;
        pq.push({startTime, source});

        while (!pq.empty())
        {
            const auto [currentTime, currentNode] = pq.top();
            pq.pop();
            if (currentTime > bestArrival[currentNode] + 1e-9)
            {
                continue;
            }

            for (const auto& window : m_windows)
            {
                NodeId neighbor = -1;
                if (window.a == currentNode)
                {
                    neighbor = window.b;
                }
                else if (window.b == currentNode)
                {
                    neighbor = window.a;
                }
                else
                {
                    continue;
                }

                const double arrivalTime = NextContactTime(currentTime, window);
                if (arrivalTime + 1e-9 < bestArrival[neighbor])
                {
                    bestArrival[neighbor] = arrivalTime;
                    parent[neighbor] = currentNode;
                    parentWindowId[neighbor] = window.id;
                    pq.push({arrivalTime, neighbor});
                }
            }
        }

        if (!std::isfinite(bestArrival[sink]))
        {
            return plan;
        }

        std::vector<RouteStep> reverseSteps;
        NodeId cursor = sink;
        while (cursor != -1)
        {
            reverseSteps.push_back({cursor, bestArrival[cursor], parentWindowId[cursor]});
            if (cursor == source)
            {
                break;
            }
            cursor = parent[cursor];
        }

        if (reverseSteps.empty() || reverseSteps.back().node != source)
        {
            return plan;
        }

        std::reverse(reverseSteps.begin(), reverseSteps.end());
        plan.reachable = true;
        plan.totalArrivalTime = bestArrival[sink];
        plan.steps = std::move(reverseSteps);
        return plan;
    }

    std::string PathToString(const std::vector<NodeId>& path) const
    {
        std::ostringstream oss;
        for (std::size_t i = 0; i < path.size(); ++i)
        {
            if (i > 0)
            {
                oss << "->";
            }
            oss << NodeLabel(path[i]);
        }
        return oss.str();
    }

    std::string PathToString(const RoutePlan& plan) const
    {
        std::vector<NodeId> path;
        path.reserve(plan.steps.size());
        for (const auto& step : plan.steps)
        {
            path.push_back(step.node);
        }
        return PathToString(path);
    }

    std::string NodeLabel(NodeId nodeId) const
    {
        if (nodeId >= 0)
        {
            if (nodeId == m_sinkNode)
            {
                return "S";
            }

            return std::string("n") + std::to_string(nodeId + 1);
        }
        return "invalid";
    }

  private:
    double m_periodSeconds{60.0};
    NodeId m_maxNodeId{-1};
        NodeId m_sinkNode{16};
    std::vector<EncounterWindow> m_windows;
    std::map<int, EncounterWindow> m_windowById;
};

class MaliciousDetector
{
  public:
    MaliciousDetector(double residualThresholdSeconds, std::uint32_t breachThreshold)
        : m_residualThresholdSeconds(residualThresholdSeconds), m_breachThreshold(breachThreshold)
    {
    }

    MaliciousDetector(ThresholdModel thresholdModel, std::uint32_t breachThreshold)
                : m_residualThresholdSeconds(1.0),
                    m_breachThreshold(breachThreshold),
                    m_thresholdModel(std::move(thresholdModel)),
                    m_useAdaptiveThresholds(true)
    {
    }

    void ObservePacket(const PacketLogger& logger,
                       PacketId packetId,
                       const TimeWindowGraph& graph,
                       NodeId source,
                       NodeId sink)
    {
        const auto& hops = logger.HopsForPacket(packetId);
        if (hops.empty())
        {
            return;
        }

        double currentArrivalTime = hops.front().sendTime;
        NodeId currentNode = source;

        std::vector<NodeId> observedPath;
        observedPath.push_back(source);
        for (const auto& hop : hops)
        {
            observedPath.push_back(hop.nextHop);
        }

        RoutePlan fullExpected = graph.ComputeExpectedRoute(source, sink, currentArrivalTime);
        const std::string observedPathText = graph.PathToString(observedPath);
        const std::string expectedPathText = graph.PathToString(fullExpected);

        std::cout << "Packet " << packetId << " expected path:  " << expectedPathText << '\n';
        std::cout << "Packet " << packetId << " observed path:  " << observedPathText << '\n';

        for (std::size_t hopIndex = 0; hopIndex < hops.size(); ++hopIndex)
        {
            const HopLogEntry& hop = hops[hopIndex];
            const EncounterWindow* window = graph.FindWindow(hop.encounterWindowId);
            if (window == nullptr)
            {
                continue;
            }

            const double expectedSendTime = graph.NextContactTime(currentArrivalTime, *window);
            const double residualDelay = hop.sendTime - expectedSendTime;
            const double thresholdSeconds = m_useAdaptiveThresholds ? m_thresholdModel.ThresholdFor(hop.from)
                                                                     : m_residualThresholdSeconds;
            const bool delayBreached = residualDelay > thresholdSeconds;

            RoutePlan expectedSuffix = graph.ComputeExpectedRoute(currentNode, sink, currentArrivalTime);
            NodeId expectedNextHop = -1;
            if (expectedSuffix.steps.size() >= 2)
            {
                expectedNextHop = expectedSuffix.steps[1].node;
            }

            const bool pathDeviated = (expectedNextHop != hop.nextHop);

            std::cout << "  hop " << hopIndex << ": " << graph.NodeLabel(hop.from)
                      << " -> " << graph.NodeLabel(hop.nextHop)
                      << " | expected send=" << std::fixed << std::setprecision(3) << expectedSendTime
                      << " observed send=" << hop.sendTime
                      << " residual=" << residualDelay
                      << " threshold=" << thresholdSeconds
                      << " nextHopMatch=" << (pathDeviated ? "no" : "yes") << '\n';

            if (delayBreached)
            {
                NodeScore& score = m_scores[hop.from];
                score.residualSum += residualDelay;
                score.samples += 1;
                score.breaches += 1;
                if (score.breaches >= m_breachThreshold)
                {
                    score.flagged = true;
                }
            }

            currentNode = hop.nextHop;
            currentArrivalTime = hop.receiveTime;
        }
    }

    void PrintReport(const TimeWindowGraph& graph) const
    {
        std::cout << "\n=== Malicious Node Report ===\n";
        for (const auto& [nodeId, score] : m_scores)
        {
            std::cout << graph.NodeLabel(nodeId)
                      << " samples=" << score.samples
                      << " breaches=" << score.breaches
                      << " residualSum=" << std::fixed << std::setprecision(3) << score.residualSum
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
    double m_residualThresholdSeconds{1.0};
    std::uint32_t m_breachThreshold{2};
        ThresholdModel m_thresholdModel;
        bool m_useAdaptiveThresholds{false};
    std::map<NodeId, NodeScore> m_scores;
};

} // namespace datamut

#endif // DATAMUT_ANALYSIS_H