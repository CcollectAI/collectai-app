import { supabase } from "@/lib/supabase";

export async function uploadCapture(
  userId: string,
  sessionId: string,
  file: { uri: string; name?: string; type?: string }
) {
  const path = `captures/${userId}/${sessionId}/${file.name ?? "photo.jpg"}`;
  const fileResp = await fetch(file.uri);
  const blob = await fileResp.blob();
  const { data, error } = await supabase.storage.from("captures").upload(path, blob, {
    contentType: file.type ?? "image/jpeg",
    upsert: true
  });
  if (error) throw error;
  return { path: data.path };
}
