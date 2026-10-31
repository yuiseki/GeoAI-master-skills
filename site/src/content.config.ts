import { defineCollection } from 'astro:content';
import { glob } from 'astro/loaders';
import { z } from 'astro/zod';

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
  }),
});

export const collections = { reports };
