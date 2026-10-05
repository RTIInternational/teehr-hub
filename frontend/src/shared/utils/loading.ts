export type LoadingStateLike =
  | boolean
  | {
      isLoading?: boolean;
    }
  | null
  | undefined;

const toLoadingBoolean = (state: LoadingStateLike): boolean =>
  typeof state === 'boolean' ? state : Boolean(state?.isLoading);

export const combineLoadingStates = (...states: LoadingStateLike[]) =>
  states.some((state) => toLoadingBoolean(state));
