import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Lean production image: only the traced subset of node_modules needed
  // to run `node server.js` gets copied into the final Docker stage,
  // instead of the whole node_modules tree.
  output: "standalone",
};

export default nextConfig;
