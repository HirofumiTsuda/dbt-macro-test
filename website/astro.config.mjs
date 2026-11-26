// The documentation site (#97): Starlight over the Markdown of ../docs, the README and the changelog.
// `prepare.py` writes src/content/docs from those files before the build; they stay plain Markdown
// that reads on GitHub.
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import starlightLinksValidator from 'starlight-links-validator';

export default defineConfig({
  site: process.env.SITE_URL ?? 'https://hirofumitsuda.github.io',
  base: process.env.BASE_PATH ?? '/dbt-macro-test',
  integrations: [
    starlight({
      title: 'dbt-macro-test',
      description: 'Test your dbt macros.',
      customCss: ['./src/styles/theme.css'],
      components: { ThemeProvider: './src/components/ThemeProvider.astro' },
      expressiveCode: { themes: ['github-dark', 'github-light'] },
      social: [
        { icon: 'github', label: 'GitHub', href: 'https://github.com/HirofumiTsuda/dbt-macro-test' },
      ],
      editLink: { baseUrl: 'https://github.com/HirofumiTsuda/dbt-macro-test/edit/main/docs/' },
      sidebar: [
        { label: 'Home', slug: '' },
        { label: 'Guide', slug: 'guide' },
        { label: 'Spec reference', slug: 'spec' },
        { label: 'Design', slug: 'design' },
        { label: 'Changelog', slug: 'changelog' },
        {
          label: 'Project',
          items: [
            { label: 'Releasing', slug: 'releasing' },
            { label: 'Design log', slug: 'history/design-log' },
          ],
        },
      ],
      plugins: [starlightLinksValidator()],
    }),
  ],
});
