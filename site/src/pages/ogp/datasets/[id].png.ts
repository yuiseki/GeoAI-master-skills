import type { APIRoute } from 'astro';
import { getCollection } from 'astro:content';
import { renderOgpPng } from '../../../lib/ogp';

export async function getStaticPaths() {
  const datasets = await getCollection('datasets');
  return datasets.map((dataset) => ({
    params: { id: dataset.id },
    props: { title: dataset.body?.match(/^# (.+)$/m)?.[1] ?? dataset.data.id },
  }));
}

export const GET: APIRoute = async ({ props }) => {
  const { title } = props as { title: string };
  return new Response(await renderOgpPng({ title }), { headers: { 'Content-Type': 'image/png' } });
};
