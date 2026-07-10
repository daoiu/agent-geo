import { Link, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';

import { api } from '@/api/client';
import { ScoreRadarChart } from '@/components/ScoreRadarChart';
import { SuggestionCard } from '@/components/SuggestionCard';
import { formatDate, scoreColor } from '@/lib/utils';

export default function ReportView() {
  const { reportId = '' } = useParams<{ reportId: string }>();

  const { data: report, error, isLoading } = useQuery({
    queryKey: ['report', reportId],
    queryFn: () => api.getReport(reportId),
  });

  if (isLoading) {
    return <div className="p-8 text-center text-muted-foreground">加载报告中...</div>;
  }

  if (error || !report) {
    return (
      <div className="p-8">
        <div className="bg-red-50 p-4 rounded-md text-red-700">
          报告加载失败：{String(error)}
        </div>
        <Link to="/" className="text-primary mt-4 inline-block">← 返回首页</Link>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-muted py-8">
      <div className="max-w-4xl mx-auto px-4">
        {/* Header */}
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <div className="flex justify-between items-start">
            <div>
              <h1 className="text-3xl font-bold text-foreground mb-2">
                {report.brand.name}
              </h1>
              <p className="text-muted-foreground">
                {report.brand.industry} · {report.brand.official_url}
              </p>
              <p className="text-sm text-muted-foreground mt-1">
                {formatDate(report.created_at)}
              </p>
            </div>
            {report.pdf_available && (
              <a
                href={api.getPdfUrl(report.id)}
                download
                className="px-4 py-2 bg-primary text-white rounded-md hover:bg-primary"
              >
                下载 PDF
              </a>
            )}
            <Link
              to={`/tasks/new?from_diagnosis=${report.id}&topic=${encodeURIComponent(report.brand.name)}`}
              className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700"
            >
              基于此诊断创建生成任务
            </Link>
          </div>
        </div>

        {/* Overall score */}
        <div className="bg-white rounded-lg shadow p-6 mb-6 text-center">
          <p className="text-muted-foreground mb-2">综合 GEO 评分</p>
          <div className={`text-6xl font-bold ${scoreColor(report.score_card.overall)}`}>
            {report.score_card.overall.toFixed(1)}
            <span className="text-2xl text-muted-foreground">/100</span>
          </div>
        </div>

        {/* Summary */}
        <div className="bg-accent border-l-4 border-blue-500 rounded-md p-4 mb-6">
          <h3 className="font-semibold text-blue-900 mb-2">执行摘要</h3>
          <p className="text-blue-800">{report.summary}</p>
        </div>

        {/* Radar chart */}
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h2 className="text-xl font-semibold mb-4">五维度评分</h2>
          <ScoreRadarChart scoreCard={report.score_card} />

          {/* Dimension details */}
          <div className="mt-6 space-y-3">
            {([
              ['authority', report.score_card.authority],
              ['relevance', report.score_card.relevance],
              ['structure', report.score_card.structure],
              ['freshness', report.score_card.freshness],
              ['verifiability', report.score_card.verifiability],
            ] as const).map(([key, dim]) => (
              <div key={key} className="border-l-4 border-blue-500 pl-4">
                <div className="flex justify-between items-baseline">
                  <strong className="text-foreground">{dim.name}</strong>
                  <span className={`text-lg font-bold ${scoreColor(dim.score * 10)}`}>
                    {dim.score.toFixed(1)}/10
                  </span>
                </div>
                {dim.evidence.length > 0 && (
                  <ul className="text-sm text-muted-foreground mt-1 space-y-1">
                    {dim.evidence.map((ev, i) => (
                      <li key={i}>• {ev}</li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Mentions */}
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h2 className="text-xl font-semibold mb-4">
            AI 提及率（{(report.score_card.mention_rate * 100).toFixed(0)}%）
          </h2>
          <div className="space-y-2">
            {report.mentions.map((m, idx) => (
              <div
                key={idx}
                className={`p-3 rounded-md ${
                  m.brand_mentioned ? 'bg-green-50 border border-green-200' : 'bg-muted border'
                }`}
              >
                <div className="flex justify-between text-sm">
                  <span className="font-medium">{m.question}</span>
                  <span className="text-muted-foreground">
                    {m.llm_provider} · {m.brand_mentioned ? `✓ 位置 ${m.mention_position}` : '✗'}
                    {m.error && ' (错误)'}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Suggestions */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold mb-4">
            优化建议（{report.suggestions.length} 条）
          </h2>
          {report.suggestions.map((s, idx) => (
            <SuggestionCard key={idx} suggestion={s} />
          ))}
        </div>

        <div className="mt-8 text-center">
          <Link to="/" className="text-primary hover:underline">
            ← 返回报告列表
          </Link>
        </div>
      </div>
    </div>
  );
}
