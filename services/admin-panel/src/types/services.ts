export type EndpointDescriptor = {
  id: string;
  method: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';
  path: string;
  description: string;
  sampleBody?: Record<string, unknown>;
};

export type ServiceDescriptor = {
  key: string;
  name: string;
  summary: string;
  focus: string;
  endpoints: EndpointDescriptor[];
  notes?: string[];
};