import type { APIRoute } from 'astro';
import { getCollection } from 'astro:content';
import { renderOgpPng } from '../../lib/ogp';

export const GET: APIRoute = async () => {
  const count = (await getCollection('datasets')).length;
  const png = await renderOgpPng({ title: '使ったデータセット', subtitle: `公開した調査レポートで実際に使った${count}件のデータカード` });
  return new Response(png, { headers: { 'Content-Type': 'image/png' } });
};
