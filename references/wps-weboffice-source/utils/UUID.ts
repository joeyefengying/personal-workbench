import uuidv1 from 'uuid/v1';

/**
 * 生成UUID
 *
 * @export
 * @returns {string}
 */
export function uuid(): string {
  return uuidv1();
}



// WEBPACK FOOTER //
// ./src/utils/UUID.ts