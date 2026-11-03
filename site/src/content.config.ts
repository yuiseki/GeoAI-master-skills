import { defineCollection, reference } from 'astro:content';
import { glob } from 'astro/loaders';
import { z } from 'astro/zod';
import { CARDS_ROOT, PUBLISHED_CARDS, datasetSlug } from './lib/datasets.mjs';

/** Data cards from the dataset-discovery skill, read in place; only the ones the reports use. */
const datasets = defineCollection({
  loader: glob({
    pattern: PUBLISHED_CARDS.map((card) => `${card}.md`),
    base: CARDS_ROOT,
    generateId: ({ data }) => datasetSlug(String(data.id)),
  }),
  schema: z.looseObject({
    kind: z.literal('dataset'),
    id: z.string(),
    description: z.string(),
    url: z.string(),
    license: z.string(),
    card_revision: z.string().optional(),
  }),
});

const reports = defineCollection({
  loader: glob({ pattern: '*.md', base: './src/content/reports' }),
  schema: z.object({
    title: z.string(),
    summary: z.string(),
    /** When the report first went up on the site; the home page lists the newest first. */
    published: z.coerce.date(),
    image: z.string(),
    imageAlt: z.string(),
    imageWidth: z.number().int().positive(),
    imageHeight: z.number().int().positive(),
    source: z.url(),
    /** Datasets the analysis actually read; each gets a page at /datasets/{id}/. */
    datasets: z.array(reference('datasets')).min(1),
  }),
});

export const collections = { reports, datasets };
