import type { APIRoute } from 'astro';
import { renderOgpPng } from '../../lib/ogp';

export const GET: APIRoute = async () =>
  new Response(await renderOgpPng({ title: '地理空間データを使った研究', labels: ['公開中の研究'] }), {
    headers: { 'Content-Type': 'image/png' },
  });
