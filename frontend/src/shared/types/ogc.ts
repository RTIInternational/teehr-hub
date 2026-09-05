export type CqlFilters = {
  [key: string]: unknown;
};

export type OgcLink = {
  href: string;
  rel: string;
  type: string;
  title?: string;
  hreflang?: string;
};

export type OgcResponse<T> = {
  items: T[];
  numberReturned: number;
  links: OgcLink[];
};
