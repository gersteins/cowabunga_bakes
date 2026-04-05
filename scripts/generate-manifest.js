#!/usr/bin/env node
// Generates docs/photos/photos.json from the contents of docs/photos/
// Run from the repo root: node scripts/generate-manifest.js

const fs = require('fs');
const path = require('path');

const photosDir = path.join(__dirname, '../docs/photos');
const outputFile = path.join(photosDir, 'photos.json');

const files = fs.readdirSync(photosDir).filter(f => /\.(jpg|jpeg|png)$/i.test(f));
const photos = files.map(file => ({ filename: file }));

// Sort descending by filename — works because filenames start with YYYY-MM-DD
photos.sort((a, b) => b.filename.localeCompare(a.filename));

fs.writeFileSync(outputFile, JSON.stringify(photos, null, 2));
console.log(`Generated ${photos.length} photos → ${outputFile}`);
console.log(`Newest: ${photos[0].filename}`);
