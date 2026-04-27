/** Brigade — TypeScript port of the Python brigade composer.
 *
 * NL → SAL via parser + 26 namespace stations + orchestrator + validator.
 * Faithful port of sdk/python/osmp/brigade/.
 */
export { parse } from "./parser.js";
export type {
  ParsedRequest, FrameProposal, Target, SlotValue, Condition,
} from "./request.js";
export { Orchestrator } from "./orchestrator.js";
export type { ComposeResult } from "./orchestrator.js";
export { defaultRegistry, BrigadeRegistry } from "./stations/index.js";
export type { Station } from "./stations/index.js";
