import type { Config } from "jest";
import nextJest from "next/jest.js";

const createJestConfig = nextJest({ dir: "./" });

const config: Config = {
  testEnvironment: "jsdom",
  setupFilesAfterEnv: ["<rootDir>/__tests__/setup.ts"],
  testMatch: ["**/__tests__/**/*.test.tsx", "**/__tests__/**/*.test.ts"],
  moduleNameMapper: {
    "^@/(.*)$": "<rootDir>/$1",
    "^lightweight-charts$": "<rootDir>/__mocks__/lightweight-charts.ts",
  },
  collectCoverageFrom: [
    "components/**/*.tsx",
    "hooks/**/*.ts",
    "lib/**/*.ts",
  ],
};

export default createJestConfig(config);
