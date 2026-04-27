/** Station registry — instantiates all 26 stations. */
import { BrigadeRegistry } from "./base.js";
import { RStation } from "./r_station.js";
import {
  EStation, HStation, GStation, VStation, WStation, NStation, AStation,
} from "./sensing.js";
import {
  CStation, TStation, IStation, SStation, KStation, BStation,
  UStation, LStation, MStation, DStation, JStation, FStation,
  OStation, PStation, QStation, XStation, YStation, ZStation,
} from "./support.js";

export { BrigadeRegistry };
export type { Station } from "./base.js";

export function defaultRegistry(): BrigadeRegistry {
  const reg = new BrigadeRegistry();
  for (const cls of [
    new RStation(),
    new EStation(), new HStation(), new GStation(), new VStation(),
    new WStation(), new NStation(), new AStation(),
    new CStation(), new TStation(), new IStation(), new SStation(),
    new KStation(), new BStation(), new UStation(), new LStation(),
    new MStation(), new DStation(), new JStation(), new FStation(),
    new OStation(), new PStation(), new QStation(), new XStation(),
    new YStation(), new ZStation(),
  ]) {
    reg.register(cls);
  }
  return reg;
}
