import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';

import { WizardShell } from '@/components/WizardShell';
import { WizardStep } from '@/components/WizardStep';
import { api } from '@/api/client';
import type { DiagnosisRequest } from '@/types/diagnosis';

const STEP_TITLES = ['品牌信息', '目标问题', '确认提交'];

export default function NewDiagnosis() {
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [form, setForm] = useState<DiagnosisRequest>({
    brand_name: '',
    industry: '',
    official_url: '',
    target_questions: ['', '', ''],
    competitors: [],
    contact_email: '',
  });

  const submit = useMutation({
    mutationFn: (req: DiagnosisRequest) => api.submitDiagnosis(req),
    onSuccess: (data) => {
      navigate(`/diagnosis/${data.task_id}/status`);
    },
  });

  const update = <K extends keyof DiagnosisRequest>(key: K, value: DiagnosisRequest[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const updateQuestion = (idx: number, value: string) => {
    const next = [...form.target_questions];
    next[idx] = value;
    update('target_questions', next);
  };

  const [competitorInput, setCompetitorInput] = useState('');

  const addCompetitor = () => {
    const trimmed = competitorInput.trim();
    if (trimmed && !form.competitors.includes(trimmed)) {
      update('competitors', [...form.competitors, trimmed]);
      setCompetitorInput('');
    }
  };

  const removeCompetitor = (competitor: string) => {
    update('competitors', form.competitors.filter((c) => c !== competitor));
  };

  const canNextFromStep1 =
    form.brand_name.trim().length >= 1 &&
    form.industry.trim().length >= 1 &&
    /^https?:\/\/.+/.test(form.official_url);

  const canNextFromStep2 = form.target_questions.filter((q) => q.trim().length >= 5).length >= 3;

  return (
    <WizardShell currentStep={step} totalSteps={STEP_TITLES.length} stepTitles={STEP_TITLES}>
      {step === 0 && (
        <WizardStep
          title="品牌信息"
          description="告诉我们您要诊断的品牌"
          onNext={() => setStep(1)}
          nextDisabled={!canNextFromStep1}
        >
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1">品牌名 *</label>
              <input
                type="text"
                value={form.brand_name}
                onChange={(e) => update('brand_name', e.target.value)}
                className="w-full px-3 py-2 border rounded-md"
                placeholder="如：小米"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">行业 *</label>
              <input
                type="text"
                value={form.industry}
                onChange={(e) => update('industry', e.target.value)}
                className="w-full px-3 py-2 border rounded-md"
                placeholder="如：消费电子"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">官网 URL *</label>
              <input
                type="url"
                value={form.official_url}
                onChange={(e) => update('official_url', e.target.value)}
                className="w-full px-3 py-2 border rounded-md"
                placeholder="https://www.example.com"
              />
            </div>
          </div>
        </WizardStep>
      )}

      {step === 1 && (
        <WizardStep
          title="目标问题"
          description="用户最常问的 3-5 个问题（AI 会基于这些问题测试提及率）"
          onBack={() => setStep(0)}
          onNext={() => setStep(2)}
          nextDisabled={!canNextFromStep2}
        >
          <div className="space-y-3">
            {form.target_questions.map((q, idx) => (
              <div key={idx}>
                <label className="block text-sm font-medium mb-1">问题 {idx + 1}</label>
                <input
                  type="text"
                  value={q}
                  onChange={(e) => updateQuestion(idx, e.target.value)}
                  className="w-full px-3 py-2 border rounded-md"
                  placeholder={`如：${idx === 0 ? 'XX 品牌怎么样' : idx === 1 ? 'XX 值得买吗' : 'XX vs 竞品'}`}
                />
              </div>
            ))}
          </div>
          <div className="mt-4 pt-4 border-t">
            <label className="block text-sm font-medium mb-1">可选：竞品品牌</label>
            <div className="flex gap-2">
              <input
                type="text"
                value={competitorInput}
                onChange={(e) => setCompetitorInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), addCompetitor())}
                className="flex-1 px-3 py-2 border rounded-md"
                placeholder="如：华为"
              />
              <button
                type="button"
                onClick={addCompetitor}
                className="px-4 py-2 bg-muted border rounded-md text-sm hover:bg-accent"
              >
                添加
              </button>
            </div>
            {form.competitors.length > 0 && (
              <div className="flex flex-wrap gap-2 mt-2">
                {form.competitors.map((c) => (
                  <span
                    key={c}
                    className="inline-flex items-center gap-1 px-2 py-1 bg-accent text-blue-700 rounded-full text-sm"
                  >
                    {c}
                    <button
                      type="button"
                      onClick={() => removeCompetitor(c)}
                      className="hover:text-blue-900 font-medium"
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>
        </WizardStep>
      )}

      {step === 2 && (
        <WizardStep
          title="确认提交"
          description="检查信息无误后开始诊断"
          onBack={() => setStep(1)}
          onNext={() => submit.mutate(form)}
          nextDisabled={submit.isPending}
          isLastStep
        >
          <div className="bg-muted p-4 rounded-md space-y-2 text-sm">
            <div><strong>品牌：</strong>{form.brand_name} ({form.industry})</div>
            <div><strong>官网：</strong>{form.official_url}</div>
            <div><strong>目标问题：</strong>
              <ul className="list-disc list-inside mt-1">
                {form.target_questions.filter((q) => q.trim()).map((q, i) => (
                  <li key={i}>{q}</li>
                ))}
              </ul>
            </div>
            <div><strong>竞品：</strong>{form.competitors.length > 0 ? form.competitors.join('、') : '无'}</div>
          </div>
          {submit.isError && (
            <div className="mt-4 p-3 bg-red-50 text-red-700 rounded-md text-sm">
              提交失败：{String(submit.error)}
            </div>
          )}
        </WizardStep>
      )}
    </WizardShell>
  );
}
