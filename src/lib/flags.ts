let cache: Record<string, boolean> = {}
export async function getFlags(jwt:string, anonKey:string, base:string){
  const r = await fetch(`${base}/functions/v1/flags`, { headers:{ Authorization:`Bearer ${jwt}`, apikey:anonKey }})
  const j = await r.json()
  return (j?.flags ?? {}) as Record<string, boolean>
}
