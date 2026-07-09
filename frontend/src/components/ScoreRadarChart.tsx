import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  ResponsiveContainer,
} from 'recharts';

import type { ScoreCard } from '@/types/diagnosis';

interface Props {
  scoreCard: ScoreCard;
}

export function ScoreRadarChart({ scoreCard }: Props) {
  const data = [
    { dim: scoreCard.authority.name, score: scoreCard.authority.score },
    { dim: scoreCard.relevance.name, score: scoreCard.relevance.score },
    { dim: scoreCard.structure.name, score: scoreCard.structure.score },
    { dim: scoreCard.freshness.name, score: scoreCard.freshness.score },
    { dim: scoreCard.verifiability.name, score: scoreCard.verifiability.score },
  ];

  return (
    <ResponsiveContainer width="100%" height={300}>
      <RadarChart data={data}>
        <PolarGrid />
        <PolarAngleAxis dataKey="dim" />
        <PolarRadiusAxis angle={90} domain={[0, 10]} />
        <Radar name="评分" dataKey="score" stroke="#2563eb" fill="#2563eb" fillOpacity={0.4} />
      </RadarChart>
    </ResponsiveContainer>
  );
}
