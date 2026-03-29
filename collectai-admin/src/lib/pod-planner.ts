// ---------------------------------------------------------------------------
// Pod Management & Content Pipeline — types, demo data, queries
// ---------------------------------------------------------------------------

import { getSupabase, isSupabaseConfigured } from "@/lib/supabase";

// ─── Types ──────────────────────────────────────────────────────────────────

export type PipelineStatus =
  | "idea"
  | "scripted"
  | "filming"
  | "editing"
  | "ready"
  | "posted"
  | "tracking";

export const PIPELINE_STAGES: { id: PipelineStatus; label: string; color: string }[] = [
  { id: "idea", label: "Idea", color: "bg-gray-100 text-gray-600" },
  { id: "scripted", label: "Scripted", color: "bg-blue-100 text-blue-700" },
  { id: "filming", label: "Filming", color: "bg-purple-100 text-purple-700" },
  { id: "editing", label: "Editing", color: "bg-amber-100 text-amber-700" },
  { id: "ready", label: "Ready", color: "bg-cyan-100 text-cyan-700" },
  { id: "posted", label: "Posted", color: "bg-emerald-100 text-emerald-700" },
  { id: "tracking", label: "Tracking", color: "bg-rose-100 text-rose-700" },
];

export type Priority = "low" | "normal" | "high" | "urgent";

export interface PipelineItem {
  id: string;
  title: string;
  description: string;
  podId: string;
  podName: string;
  creatorId: string;
  creatorName: string;
  creatorHandle: string;
  accountId: string;
  hookText: string;
  hookType: string;
  format: string;
  conceptCluster: string;
  kitSlug: string;
  niche: string;
  country: string;
  status: PipelineStatus;
  dueDate: string;
  postedDate: string;
  videoId: string;
  priority: Priority;
  notes: string;
  createdAt: string;
}

export interface Pod {
  id: string;
  name: string;
  language: string;
  description: string;
  color: string;
  targetVideosPerWeek: number;
  isActive: boolean;
  members: PodMember[];
  // Computed
  videosThisWeek: number;
  videosThisMonth: number;
  pipelineCount: Record<PipelineStatus, number>;
  totalRevenue: number;
  avgHitRate: number;
}

export interface PodMember {
  id: string;
  creatorId: string;
  name: string;
  handle: string;
  platform: string;
  role: string;
  videosCount: number;
  hitRate: number;
  totalViews: number;
}

export interface PodPlannerData {
  pods: Pod[];
  pipeline: PipelineItem[];
  stats: {
    totalPods: number;
    activePods: number;
    totalCreators: number;
    totalPipelineItems: number;
    itemsByStatus: Record<PipelineStatus, number>;
    overdueItems: number;
    videosThisWeek: number;
    videosThisMonth: number;
  };
}

// ─── Demo Data ──────────────────────────────────────────────────────────────

function getDemoPodData(): PodPlannerData {
  const pods: Pod[] = [
    {
      id: "pod-de", name: "DE Pod", language: "DE", description: "German-speaking creators", color: "#FF6B6B",
      targetVideosPerWeek: 5, isActive: true,
      members: [
        { id: "m1", creatorId: "c1", name: "Luna Craft", handle: "@lunacraft_de", platform: "tiktok", role: "lead", videosCount: 12, hitRate: 25, totalViews: 156000 },
        { id: "m2", creatorId: "c2", name: "Wolke Wolle", handle: "@wolkewolle", platform: "tiktok", role: "creator", videosCount: 8, hitRate: 12, totalViews: 89000 },
        { id: "m3", creatorId: "c3", name: "Garn Lisa", handle: "@garnlisa", platform: "instagram", role: "creator", videosCount: 6, hitRate: 17, totalViews: 67000 },
      ],
      videosThisWeek: 3, videosThisMonth: 14,
      pipelineCount: { idea: 2, scripted: 1, filming: 1, editing: 0, ready: 1, posted: 3, tracking: 2 },
      totalRevenue: 1206, avgHitRate: 18,
    },
    {
      id: "pod-fr", name: "FR Pod", language: "FR", description: "French-speaking creators", color: "#1E3A8A",
      targetVideosPerWeek: 4, isActive: true,
      members: [
        { id: "m4", creatorId: "c4", name: "Maille Douce", handle: "@maille.douce", platform: "tiktok", role: "lead", videosCount: 10, hitRate: 30, totalViews: 198000 },
        { id: "m5", creatorId: "c5", name: "Fil et Aiguille", handle: "@fil.aiguille", platform: "tiktok", role: "creator", videosCount: 5, hitRate: 20, totalViews: 54000 },
      ],
      videosThisWeek: 2, videosThisMonth: 9,
      pipelineCount: { idea: 3, scripted: 2, filming: 0, editing: 1, ready: 0, posted: 2, tracking: 1 },
      totalRevenue: 702, avgHitRate: 25,
    },
    {
      id: "pod-nl", name: "NL Pod", language: "NL", description: "Dutch-speaking creators", color: "#FF8C42",
      targetVideosPerWeek: 3, isActive: true,
      members: [
        { id: "m6", creatorId: "c6", name: "Haak Mee", handle: "@haakmee.nl", platform: "tiktok", role: "lead", videosCount: 7, hitRate: 14, totalViews: 72000 },
      ],
      videosThisWeek: 1, videosThisMonth: 5,
      pipelineCount: { idea: 1, scripted: 1, filming: 1, editing: 0, ready: 0, posted: 1, tracking: 0 },
      totalRevenue: 432, avgHitRate: 14,
    },
  ];

  const hooks = [
    "This $3 pack had a $2,000 card inside", "How much is this ACTUALLY worth?", "I found this at a garage sale for $5",
    "This just got VAULTED", "My collection in 15 seconds", "The AI says my collection is worth HOW MUCH?",
    "PSA just graded my childhood card...", "The seller had NO idea what they had",
  ];
  const formats = ["tutorial", "POV", "transition", "unboxing", "timelapse", "GRWM"];
  const clusters = ["beginner-journey", "evening-routine", "gift-idea", "stress-relief"];
  const kits = ["momo-frog", "luna-bunny", "kiki-cat", "sakura-bear"];
  const statuses: PipelineStatus[] = ["idea", "idea", "scripted", "scripted", "filming", "editing", "ready", "posted", "posted", "tracking", "idea", "scripted", "filming", "ready", "posted", "tracking"];

  const now = new Date();
  const pipeline: PipelineItem[] = statuses.map((status, i) => {
    const pod = pods[i % pods.length];
    const member = pod.members[i % pod.members.length];
    const dueDate = new Date(now.getTime() + (i - 8) * 86400000);
    return {
      id: `pipe-${i}`,
      title: hooks[i % hooks.length],
      description: `${formats[i % formats.length]} style video for ${kits[i % kits.length]}`,
      podId: pod.id,
      podName: pod.name,
      creatorId: member.creatorId,
      creatorName: member.name,
      creatorHandle: member.handle,
      accountId: `@collectai.${pod.language.toLowerCase()}`,
      hookText: hooks[i % hooks.length],
      hookType: ["question", "POV", "statement", "suspense", "list"][i % 5],
      format: formats[i % formats.length],
      conceptCluster: clusters[i % clusters.length],
      kitSlug: kits[i % kits.length],
      niche: "collectibles",
      country: pod.language,
      status,
      dueDate: dueDate.toISOString().slice(0, 10),
      postedDate: status === "posted" || status === "tracking" ? new Date(now.getTime() - i * 86400000).toISOString().slice(0, 10) : "",
      videoId: status === "tracking" ? `tiktok-${2000 + i}` : "",
      priority: (["normal", "normal", "high", "normal", "urgent", "low"][i % 6]) as Priority,
      notes: "",
      createdAt: new Date(now.getTime() - (i + 5) * 86400000).toISOString(),
    };
  });

  const itemsByStatus: Record<PipelineStatus, number> = { idea: 0, scripted: 0, filming: 0, editing: 0, ready: 0, posted: 0, tracking: 0 };
  for (const item of pipeline) itemsByStatus[item.status]++;

  const overdue = pipeline.filter((p) => p.dueDate && p.dueDate < now.toISOString().slice(0, 10) && !["posted", "tracking"].includes(p.status)).length;

  return {
    pods,
    pipeline,
    stats: {
      totalPods: pods.length,
      activePods: pods.filter((p) => p.isActive).length,
      totalCreators: pods.reduce((s, p) => s + p.members.length, 0),
      totalPipelineItems: pipeline.length,
      itemsByStatus,
      overdueItems: overdue,
      videosThisWeek: pods.reduce((s, p) => s + p.videosThisWeek, 0),
      videosThisMonth: pods.reduce((s, p) => s + p.videosThisMonth, 0),
    },
  };
}

// ─── Fetch ──────────────────────────────────────────────────────────────────

export async function fetchPodPlannerData(): Promise<PodPlannerData> {
  if (!isSupabaseConfigured()) return getDemoPodData();

  const sb = getSupabase();
  if (!sb) return getDemoPodData();

  // Fetch pods with members
  const { data: podRows } = await sb
    .from("ugc_pods")
    .select("*, ugc_pod_members(*, creators(*))")
    .eq("is_active", true)
    .order("name");

  const { data: pipelineRows } = await sb
    .from("ugc_content_pipeline")
    .select("*, ugc_pods(name), creators(name, handle)")
    .order("created_at", { ascending: false });

  if (!podRows || !pipelineRows) return getDemoPodData();

  const pods: Pod[] = podRows.map((p: Record<string, unknown>) => {
    const members = ((p.ugc_pod_members as Record<string, unknown>[]) ?? []).map((m: Record<string, unknown>) => {
      const creator = m.creators as Record<string, unknown>;
      return {
        id: m.id as string,
        creatorId: m.creator_id as string,
        name: (creator?.name as string) ?? "",
        handle: (creator?.handle as string) ?? "",
        platform: (creator?.platform as string) ?? "tiktok",
        role: (m.role as string) ?? "creator",
        videosCount: 0,
        hitRate: 0,
        totalViews: 0,
      };
    });
    return {
      id: p.id as string,
      name: p.name as string,
      language: (p.language as string) ?? "",
      description: (p.description as string) ?? "",
      color: (p.color as string) ?? "#FF6B6B",
      targetVideosPerWeek: (p.target_videos_per_week as number) ?? 5,
      isActive: (p.is_active as boolean) ?? true,
      members,
      videosThisWeek: 0,
      videosThisMonth: 0,
      pipelineCount: { idea: 0, scripted: 0, filming: 0, editing: 0, ready: 0, posted: 0, tracking: 0 },
      totalRevenue: 0,
      avgHitRate: 0,
    };
  });

  const pipeline: PipelineItem[] = pipelineRows.map((r: Record<string, unknown>) => ({
    id: r.id as string,
    title: (r.title as string) ?? "",
    description: (r.description as string) ?? "",
    podId: (r.pod_id as string) ?? "",
    podName: ((r.ugc_pods as Record<string, string>)?.name) ?? "",
    creatorId: (r.creator_id as string) ?? "",
    creatorName: ((r.creators as Record<string, string>)?.name) ?? "",
    creatorHandle: ((r.creators as Record<string, string>)?.handle) ?? "",
    accountId: (r.account_id as string) ?? "",
    hookText: (r.hook_text as string) ?? "",
    hookType: (r.hook_type as string) ?? "",
    format: (r.format as string) ?? "",
    conceptCluster: (r.concept_cluster as string) ?? "",
    kitSlug: (r.kit_slug as string) ?? "",
    niche: (r.niche as string) ?? "collectibles",
    country: (r.country as string) ?? "",
    status: (r.status as PipelineStatus) ?? "idea",
    dueDate: (r.due_date as string) ?? "",
    postedDate: (r.posted_date as string) ?? "",
    videoId: (r.video_id as string) ?? "",
    priority: (r.priority as Priority) ?? "normal",
    notes: (r.notes as string) ?? "",
    createdAt: (r.created_at as string) ?? "",
  }));

  // Compute pipeline counts per pod
  for (const item of pipeline) {
    const pod = pods.find((p) => p.id === item.podId);
    if (pod) pod.pipelineCount[item.status]++;
  }

  const itemsByStatus: Record<PipelineStatus, number> = { idea: 0, scripted: 0, filming: 0, editing: 0, ready: 0, posted: 0, tracking: 0 };
  for (const item of pipeline) itemsByStatus[item.status]++;

  const today = new Date().toISOString().slice(0, 10);
  const overdue = pipeline.filter((p) => p.dueDate && p.dueDate < today && !["posted", "tracking"].includes(p.status)).length;

  return {
    pods,
    pipeline,
    stats: {
      totalPods: pods.length,
      activePods: pods.filter((p) => p.isActive).length,
      totalCreators: pods.reduce((s, p) => s + p.members.length, 0),
      totalPipelineItems: pipeline.length,
      itemsByStatus,
      overdueItems: overdue,
      videosThisWeek: pods.reduce((s, p) => s + p.videosThisWeek, 0),
      videosThisMonth: pods.reduce((s, p) => s + p.videosThisMonth, 0),
    },
  };
}
