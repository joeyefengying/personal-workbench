#!/usr/bin/env node
/**
 * 从轻推 app 的 localStorage LevelDB 提取所有缓存的 webofficeUrl。
 * 
 * 使用 classic-level (Node.js 原生 LevelDB 绑定) 读取，
 * 比 Python 二进制搜索更可靠（95 个 vs 13 个）。
 * 
 * 每个 fileId 缓存:
 *   {fileId}-webofficeUrl   = base64(完整 WPS 在线编辑器 URL)
 *   {fileId}-wbo_accessToken = WPS JWT
 *   {fileId}-wbo_refreshToken = WPS refreshToken
 * 
 * 用法:
 *   node ldb_reader.js            → 输出 JSON 数组
 *   node ldb_reader.js <fileId>   → 输出单个文档 JSON
 */

const { ClassicLevel } = require('classic-level');
const fs = require('fs');
const path = require('path');

const LDB_SRC = process.env.HOME + '/Library/Application Support/Qingtui/Partitions/tab--undefined/Local Storage/leveldb';
const LDB_TMP = '/tmp/ldb-copy-' + process.pid;

async function readAllDocs() {
  // Copy LevelDB to temp (avoid lock conflict with 轻推 app)
  fs.rmSync(LDB_TMP, { recursive: true, force: true });
  fs.mkdirSync(LDB_TMP, { recursive: true });
  for (const f of fs.readdirSync(LDB_SRC)) {
    if (f.endsWith('.ldb') || f.endsWith('.log') || f === 'CURRENT' || f.startsWith('MANIFEST')) {
      fs.copyFileSync(path.join(LDB_SRC, f), path.join(LDB_TMP, f));
    }
  }

  const db = new ClassicLevel(LDB_TMP, { keyEncoding: 'utf8', valueEncoding: 'utf8' });
  await db.open();

  const allDocs = {};

  for await (const [rawKey, value] of db.iterator()) {
    const cleanValue = value.replace(/^\x01/, '');
    const m = rawKey.match(/(\d{10,20})-(webofficeUrl|wbo_accessToken|wbo_refreshToken)$/);
    if (!m) continue;

    const fileId = m[1];
    const keyType = m[2];

    if (!allDocs[fileId]) allDocs[fileId] = { file_id: fileId };

    if (keyType === 'webofficeUrl') {
      const b64 = cleanValue.replace(/\n/g, '').replace(/\r/g, '');
      try {
        const decoded = Buffer.from(b64, 'base64').toString('utf8');
        allDocs[fileId].url = decoded;
        const nameMatch = decoded.match(/fileName=([^&]+)/);
        const typeMatch = decoded.match(/fileType=([^&]+)/);
        const permMatch = decoded.match(/requestPermission=([^&]+)/);
        if (nameMatch) allDocs[fileId].name = decodeURIComponent(nameMatch[1]);
        if (typeMatch) allDocs[fileId].type = typeMatch[1];
        if (permMatch) allDocs[fileId].permission = permMatch[1];
      } catch (e) { /* skip invalid base64 */ }
    } else if (keyType === 'wbo_accessToken') {
      allDocs[fileId].accessToken = cleanValue;
    } else if (keyType === 'wbo_refreshToken') {
      allDocs[fileId].refreshToken = cleanValue;
    }
  }

  await db.close();
  fs.rmSync(LDB_TMP, { recursive: true, force: true });

  // Only return docs that have webofficeUrl
  return Object.values(allDocs).filter(d => d.url);
}

async function main() {
  const docs = await readAllDocs();
  const targetId = process.argv[2];

  if (targetId) {
    // Return single doc
    const doc = docs.find(d => d.file_id === targetId);
    if (!doc) {
      console.log(JSON.stringify({ ok: false, error: '文档 ' + targetId + ' 未在轻推缓存中找到' }));
      process.exit(1);
    }
    console.log(JSON.stringify({ ok: true, ...doc }));
  } else {
    // Return all docs
    console.log(JSON.stringify({ ok: true, count: docs.length, docs }));
  }
}

main().catch(e => {
  console.log(JSON.stringify({ ok: false, error: e.message }));
  process.exit(1);
});
