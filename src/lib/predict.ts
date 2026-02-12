import { callEdge } from './api'
export async function predictPrice(jwt:string, anonKey:string, title:string, category:string, attrs?:Record<string,unknown>) {
  return callEdge<{ ok:true; price_eur:number }>('predict-price', jwt, anonKey, { title, category, attrs })
}
