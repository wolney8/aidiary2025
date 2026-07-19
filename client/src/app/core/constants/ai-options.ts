export interface AiModelOption {
  value: string;
  label: string;
  hint: string;
}

export const AI_MODEL_OPTIONS: AiModelOption[] = [
  {
    value: "gpt-4o-mini",
    label: "GPT-4o mini",
    hint: "Lower-cost general model. Best when you want lighter, faster analysis.",
  },
  {
    value: "gpt-4.1-mini",
    label: "GPT-4.1 mini",
    hint: "Balanced default. Good day-to-day depth without pushing cost as high as full GPT-4.1.",
  },
  {
    value: "gpt-4.1",
    label: "GPT-4.1",
    hint: "Highest-depth option here. Usually best for richer analysis, but it generally costs more per run.",
  },
];

export const DEFAULT_AI_MODEL = "gpt-4.1-mini";
