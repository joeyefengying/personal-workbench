import ClientVersionBO from '../models/bo/ClientVersionBO';

export function transformClientVersion(data: any): ClientVersionBO {
  return {
    latestVersion: parseInt(data.lastestVer, 10),
  };
}



// WEBPACK FOOTER //
// ./src/transformers/ClientVersionTransformer.ts