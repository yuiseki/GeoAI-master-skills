import type { APIRoute } from 'astro';
import { getCollection } from 'astro:content';
import { renderOgpPng } from '../../lib/ogp';

export async function getStaticPaths() {
  const reports = await getCollection('reports');
  return reports.map((report) => ({
    params: { slug: report.id },
    props: { title: report.data.title, labels: [report.data.topic, report.data.kicker] },
  }));
}

export const GET: APIRoute = async ({ props }) => {
  const { title, labels } = props as { title: string; labels: string[] };
  return new Response(await renderOgpPng({ title, labels }), { headers: { 'Content-Type': 'image/png' } });
};
