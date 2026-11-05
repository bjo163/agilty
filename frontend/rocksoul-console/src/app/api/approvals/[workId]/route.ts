import {createHmac,randomBytes} from "node:crypto";
import {NextRequest,NextResponse} from "next/server";
import {currentSession} from "@/lib/auth";

export const runtime="nodejs";
type Context={params:Promise<{workId:string}>};

export async function POST(req:NextRequest,ctx:Context){
  const session=await currentSession();
  if(!session||session.role!=="admin")return NextResponse.json({detail:"Administrator session required"},{status:403});
  const configuredAdminId=process.env.ROCKSOUL_CONSOLE_ADMIN_ID??"";
  if(!configuredAdminId)return NextResponse.json({detail:"ROCKSOUL_CONSOLE_ADMIN_ID must be configured"},{status:503});
  if(!session.sub||session.sub!==configuredAdminId)return NextResponse.json({detail:"Administrator session principal is stale; sign in again"},{status:403});
  const secret=process.env.ROCKSOUL_APPROVAL_SIGNING_SECRET??"";
  const apiKey=process.env.ROCKSOUL_API_KEY??"";
  if(secret.length<32||!apiKey)return NextResponse.json({detail:"Approval signing or API credentials are not configured"},{status:503});
  let body:{decision?:string};
  try{body=await req.json()}catch{return NextResponse.json({detail:"Invalid JSON body"},{status:400})}
  if(body.decision!=="approved"&&body.decision!=="rejected")return NextResponse.json({detail:"Decision must be approved or rejected"},{status:422});
  const {workId}=await ctx.params;
  if(!workId||workId.length>128||workId.includes(".."))return NextResponse.json({detail:"Invalid WorkItem ID"},{status:400});
  let origin=process.env.ROCKSOUL_API_INTERNAL_URL??"http://127.0.0.1:8765";
  while(origin.endsWith("/"))origin=origin.slice(0,-1);
  const headers={"X-ROCKSOUL-API-Key":apiKey,"Accept":"application/json"};
  try{
    const current=await fetch(origin+"/api/v1/work-items/"+encodeURIComponent(workId),{headers,cache:"no-store",signal:AbortSignal.timeout(10000)});
    const item=await current.json();
    if(!current.ok)return NextResponse.json(item,{status:current.status});
    const payload={
      decision:body.decision,
      approver_id:session.sub,
      approver_role:"admin",
      contract_digest:item.contract_digest,
      issued_at:Math.floor(Date.now()/1000),
      nonce:randomBytes(16).toString("hex"),
    };
    const canonical=JSON.stringify(Object.fromEntries(Object.entries(payload).sort(([a],[b])=>a.localeCompare(b))));
    const signature=createHmac("sha256",secret).update(canonical).digest("hex");
    const response=await fetch(origin+"/api/v1/work-items/"+encodeURIComponent(workId)+"/approval",{
      method:"POST",
      headers:{...headers,"Content-Type":"application/json","X-ROCKSOUL-Approval-Signature":signature},
      body:canonical,cache:"no-store",signal:AbortSignal.timeout(10000),
    });
    const result=await response.json();
    return NextResponse.json(result,{status:response.status,headers:{"Cache-Control":"no-store"}});
  }catch{return NextResponse.json({detail:"ROCKSOUL API upstream unavailable"},{status:502})}
}
