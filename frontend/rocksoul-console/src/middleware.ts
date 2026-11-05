import {NextRequest,NextResponse} from "next/server";

function decodeBase64Url(value:string){
  try{
    const normalized=value.replace(/-/g,"+").replace(/_/g,"/");
    const padded=normalized+"=".repeat((4-normalized.length%4)%4);
    return Uint8Array.from(atob(padded),c=>c.charCodeAt(0));
  }catch{
    return new Uint8Array();
  }
}

async function isValidSession(token:string|undefined){
  if(!token)return false;
  const [payload,signature,...extra]=token.split(".");
  const secret=process.env.ROCKSOUL_CONSOLE_SESSION_SECRET;
  if(!payload||!signature||extra.length||!secret||secret.length<32)return false;
  try{
    const key=await crypto.subtle.importKey(
      "raw",
      new TextEncoder().encode(secret),
      {name:"HMAC",hash:"SHA-256"},
      false,
      ["verify"]
    );
    const session=JSON.parse(new TextDecoder().decode(decodeBase64Url(payload))) as {role:string;exp:number};
    if(!["admin","operator"].includes(session.role)||!Number.isFinite(session.exp)||session.exp<Date.now()/1000)return false;
    return await crypto.subtle.verify("HMAC",key,decodeBase64Url(signature),new TextEncoder().encode(payload));
  }catch{
    return false;
  }
}

export async function middleware(request:NextRequest){
  const pathname=request.nextUrl.pathname;
  if(pathname==="/login"||pathname.startsWith("/api/auth/"))return NextResponse.next();
  if(await isValidSession(request.cookies.get("rocksoul_session")?.value))return NextResponse.next();
  if(pathname.startsWith("/api/"))return NextResponse.json({detail:"Authentication required"},{status:401});
  return NextResponse.redirect(new URL("/login",request.url));
}

export const config={matcher:["/","/api/v1/:path*"]};
