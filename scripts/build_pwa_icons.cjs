// Ícones geométricos do terminal, sem bibliotecas externas.
const fs = require("node:fs");
const path = require("node:path");
const zlib = require("node:zlib");
const target = path.join(__dirname, "../server/static/icons");
fs.mkdirSync(target, { recursive: true });

function crc32(bytes) {
  let value = 0xffffffff;
  for (const byte of bytes) {
    value ^= byte;
    for (let bit = 0; bit < 8; bit++) value = (value >>> 1) ^ ((value & 1) ? 0xedb88320 : 0);
  }
  return (value ^ 0xffffffff) >>> 0;
}
function chunk(type, bytes) {
  const label = Buffer.from(type);
  const size = Buffer.alloc(4);
  size.writeUInt32BE(bytes.length);
  const check = Buffer.alloc(4);
  check.writeUInt32BE(crc32(Buffer.concat([label, bytes])));
  return Buffer.concat([size, label, bytes, check]);
}
function png(size) {
  const stride = size * 4 + 1;
  const rows = Buffer.alloc(size * stride);
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const px = x / size, py = y / size;
      const rectangle = (left, top, right, bottom) => px >= left && px < right && py >= top && py < bottom;
      const frame = rectangle(.19, .26, .81, .74) && !rectangle(.215, .285, .785, .715);
      const t = rectangle(.33, .36, .58, .405) || rectangle(.4325, .36, .4775, .62);
      const cursor = rectangle(.57, .575, .67, .62);
      const offset = y * stride + 1 + x * 4;
      const color = frame || t || cursor ? [0, 255, 102] : [3, 10, 4];
      rows[offset] = color[0]; rows[offset + 1] = color[1]; rows[offset + 2] = color[2]; rows[offset + 3] = 255;
    }
  }
  const header = Buffer.alloc(13);
  header.writeUInt32BE(size, 0); header.writeUInt32BE(size, 4);
  header[8] = 8; header[9] = 6;
  return Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk("IHDR", header), chunk("IDAT", zlib.deflateSync(rows)), chunk("IEND", Buffer.alloc(0))]);
}
for (const size of [192, 512]) fs.writeFileSync(path.join(target, "icon-" + size + ".png"), png(size));
console.log("Ícones PWA gerados: 192×192 e 512×512.");
