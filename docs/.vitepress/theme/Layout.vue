<script setup>
import DefaultTheme from 'vitepress/theme-without-fonts'
import { useData, withBase } from 'vitepress'

const { Layout } = DefaultTheme
const { frontmatter } = useData()
</script>

<template>
  <Layout>
    <template #layout-bottom>
      <footer v-if="frontmatter.home" class="home-footer">
        <span>A little change of scenery.</span>
        <nav aria-label="Footer">
          <a :href="withBase('/docs/')">Documentation</a>
          <a :href="withBase('/docs/releases.html')">Release notes</a>
        </nav>
      </footer>
    </template>
  </Layout>
</template>
