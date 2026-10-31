import type { APIRoute } from 'astro';
import { renderOgpPng } from '../../lib/ogp';

// No dataset count here: social sites cache OGP images for a long time, so a number would go stale.
export const GET: APIRoute = async () => {
  const png = await renderOgpPng({ title: '使ったデータセット', subtitle: '公開した調査レポートで実際に使ったデータの一覧' });
  return new Response(png, { headers: { 'Content-Type': 'image/png' } });
};
