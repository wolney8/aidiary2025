declare const describe: (
  description: string,
  specDefinitions: () => void,
) => void;
declare const it: (expectation: string, assertion?: () => void) => void;
declare const beforeEach: (action: () => void | Promise<void>) => void;
declare const afterEach: (action: () => void | Promise<void>) => void;
declare const expect: (actual: unknown) => any;
declare const jasmine: any;
