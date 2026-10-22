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
  timeStamp?: string;
  numberReturned: number;
  numberMatched?: number;
  links: OgcLink[];
};
