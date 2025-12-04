export type SpecificationItem = {
  name: string;
  qty: number | null;
  unit: string | null;
  price: number | null;
  amount: number | null;
  country: string | null;
};

export type SpecificationJson = {
  items: SpecificationItem[];
  total: number | null;
  vat: number | null;
  warning: string | null;
};

export type SplitResponse = Record<string, string | SpecificationJson | null>;
export type SpecificationResponse = { spec_json: SpecificationJson | null };

export type AiLegalResponse = {
  overall_score?: number;
  html: string;
};

export type DispatchServiceResult = {
  url: string | null | undefined;
  status: number | null | undefined;
  response?: unknown;
  error?: string | null;
  elapsed_ms: number | null | undefined;
};

export type DispatchResponse = Record<string, DispatchServiceResult>;