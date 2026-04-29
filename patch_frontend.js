const fs = require('fs');

const path = 'frontend/pages/index.js';
let content = fs.readFileSync(path, 'utf8');

const newVectorsStr = `"AI-generated fake EU Directive draft circulating on messaging apps claims an immediate 60% tax on farm diesel starting Monday, igniting calls for tractor blockades across all major ports.",
  "A network of bot accounts on a major social media platform is aggressively amplifying a deepfake video of a prominent civil rights leader urging supporters to boycott upcoming national elections, claiming electronic voting machines are rigged.",
`;

if (!content.includes("tractor blockades")) {
    content = content.replace(/const TEST_VECTORS = \[/, `const TEST_VECTORS = [\n  ${newVectorsStr}`);
    fs.writeFileSync(path, content);
    console.log("Updated frontend index.js with new vectors");
} else {
    console.log("Frontend index.js already has the new vectors");
}
