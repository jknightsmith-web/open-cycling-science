import { useQuery } from "@tanstack/react-query";
import { api } from "./client";
import { zoneOf } from "../format/format";

export const useSettings = () => useQuery({ queryKey: ["settings"], queryFn: api.settings, staleTime: Infinity });
export function useZone(): string {
  const { data } = useSettings();
  return zoneOf(data);
}
export const useEntry = (id: string | null) =>
  useQuery({ queryKey: ["entry", id], queryFn: () => api.entry(id as string), enabled: !!id, staleTime: Infinity });
export const useStates = () => useQuery({ queryKey: ["states"], queryFn: api.states, staleTime: Infinity });
export const useProposedCount = () =>
  useQuery({ queryKey: ["groups", "proposed"], queryFn: () => api.groups("proposed"), select: (g) => g.length });
