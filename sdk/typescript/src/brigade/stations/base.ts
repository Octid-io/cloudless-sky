/** Station base + registry. Pure functions of ParsedRequest. */
import type { FrameProposal, ParsedRequest } from "../request.js";

export interface Station {
  namespace: string;
  propose(req: ParsedRequest): FrameProposal[];
}

export class BrigadeRegistry {
  private stations: Record<string, Station> = {};

  register(s: Station): void {
    this.stations[s.namespace] = s;
  }

  allStations(): Station[] {
    return Object.values(this.stations);
  }

  get(namespace: string): Station | null {
    return this.stations[namespace] ?? null;
  }

  proposeAll(req: ParsedRequest): Record<string, FrameProposal[]> {
    const out: Record<string, FrameProposal[]> = {};
    for (const [ns, st] of Object.entries(this.stations)) {
      try {
        const props = st.propose(req);
        if (props.length > 0) out[ns] = props;
      } catch {
        // station error → no proposal
      }
    }
    return out;
  }
}
