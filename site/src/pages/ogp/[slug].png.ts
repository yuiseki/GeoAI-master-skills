import type { APIRoute } from 'astro';
import { getCollection } from 'astro:content';
import { renderOgpPng } from '../../lib/ogp';

export async function getStaticPaths() {
  const reports = await getCollection('reports');
  return reports.map((report) => ({
    params: { slug: report.id },
    props: { title: report.data.title },
  }));
}

export const GET: APIRoute = async ({ props }) => {
  const { title } = props as { title: string };
  return new Response(await renderOgpPng({ title }), { headers: { 'Content-Type': 'image/png' } });
};
