import { createRouter, createWebHistory } from "vue-router";

import DocPage from "@/pages/DocPage.vue";
import TestPage from "@/pages/TestPage.vue";

const routes = [
  { path: "/", name: "doc", component: DocPage },
  { path: "/test", name: "test", component: TestPage },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;
