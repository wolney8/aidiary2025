export interface AiModelOption {
  value: string;
  label: string;
}

export const AI_MODEL_OPTIONS: AiModelOption[] = [
  { value: "gpt-4o-mini", label: "GPT-4o mini" },
  { value: "gpt-4.1-mini", label: "GPT-4.1 mini" },
  { value: "gpt-4.1", label: "GPT-4.1" },
];

export const DEFAULT_AI_MODEL = "gpt-4.1-mini";
