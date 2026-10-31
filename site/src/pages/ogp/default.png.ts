import type { APIRoute } from 'astro';
import { renderHomeOgpPng } from '../../lib/ogp';

export const GET: APIRoute = async () =>
  new Response(await renderHomeOgpPng(), { headers: { 'Content-Type': 'image/png' } });
