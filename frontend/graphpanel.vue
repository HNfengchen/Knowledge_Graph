<!--
  GraphPanel — 知识图谱子图可视化（Vue 3 + D3 v7 单文件组件）

  集成方式：见 frontend/README.md
  依赖：d3@7（npm 或 CDN）
  API 约定：POST {apiBaseUrl}/api/v1/kg/query
            body: {entity_name, depth, relation_types?}
            返回 ApiResponse<{nodes:[{id,name,type,props}], links:[{source,target,relation,weight}]}>
-->
<template>
  <div class="kg-graph-panel">
    <header class="kg-toolbar">
      <input v-model="entityInput" placeholder="实体名称" @keyup.enter="loadGraph" />
      <input type="number" v-model.number="depthInput" min="1" max="3" />
      <button @click="loadGraph" :disabled="loading">{{ loading ? "加载中..." : "查询" }}</button>
      <select multiple v-model="relationFilter" class="kg-rel-filter">
        <option v-for="r in availableRelations" :key="r" :value="r">{{ r }}</option>
      </select>
    </header>
    <div class="kg-canvas-wrap" ref="wrap">
      <svg ref="svgEl" :width="width" :height="height">
        <g ref="rootG">
          <line
            v-for="(l, i) in renderedLinks"
            :key="'l' + i"
            :x1="l.source.x"
            :y1="l.source.y"
            :x2="l.target.x"
            :y2="l.target.y"
            :stroke-width="Math.max(1, l.weight * 2)"
            stroke="#999"
            stroke-opacity="0.6"
          />
          <g v-for="n in nodes" :key="n.id" :transform="`translate(${n.x},${n.y})`">
            <circle :r="nodeRadius(n)" :fill="colorOf(n.type)" stroke="#fff" stroke-width="1.5" />
            <text dy="4" text-anchor="middle" font-size="10" fill="#222">{{ n.name }}</text>
          </g>
        </g>
      </svg>
      <aside v-if="selected" class="kg-detail">
        <h4>{{ selected.name }}</h4>
        <p>类型: {{ selected.type }}</p>
        <pre>{{ JSON.stringify(selected.props, null, 2) }}</pre>
        <button @click="selected = null">关闭</button>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick } from "vue";
import * as d3 from "d3";

const props = defineProps({
  apiBaseUrl: { type: String, default: "http://localhost:8000" },
  entityName: { type: String, default: "" },
  depth: { type: Number, default: 2 },
  authToken: { type: String, default: "" },
});

const entityInput = ref(props.entityName);
const depthInput = ref(props.depth);
const width = ref(900);
const height = ref(600);
const loading = ref(false);
const nodes = ref([]);
const links = ref([]);
const selected = ref(null);
const relationFilter = ref([]);
const wrap = ref(null);
const svgEl = ref(null);
const rootG = ref(null);

const availableRelations = computed(() => {
  return Array.from(new Set(links.value.map((l) => l.relation)));
});

const renderedLinks = computed(() => {
  if (relationFilter.value.length === 0) return links.value;
  return links.value.filter((l) => relationFilter.value.includes(l.relation));
});

const nodeRadius = (n) => {
  const deg = links.value.filter((l) => l.source.id === n.id || l.target.id === n.id).length;
  return 6 + Math.min(deg, 10);
};

const palette = ["#4e79a7", "#f28e2c", "#e15759", "#76b7b2", "#59a14f", "#edc949", "#af7aa1"];
const typeIndex = new Map();
const colorOf = (type) => {
  if (!typeIndex.has(type)) typeIndex.set(type, typeIndex.size);
  return palette[typeIndex.get(type) % palette.length];
};

let simulation = null;

async function loadGraph() {
  if (!entityInput.value.trim()) return;
  loading.value = true;
  try {
    const headers = { "Content-Type": "application/json" };
    if (props.authToken) headers["Authorization"] = `Bearer ${props.authToken}`;
    const res = await fetch(`${props.apiBaseUrl}/api/v1/kg/query`, {
      method: "POST",
      headers,
      body: JSON.stringify({ entity_name: entityInput.value, depth: depthInput.value }),
    });
    const env = await res.json();
    if (env.code !== 200) throw new Error(env.msg);
    const data = env.data || { nodes: [], links: [] };
    nodes.value = data.nodes.map((n) => ({ ...n }));
    links.value = data.links.map((l) => ({ ...l }));
    await nextTick();
    runSimulation();
  } finally {
    loading.value = false;
  }
}

function runSimulation() {
  if (simulation) simulation.stop();
  simulation = d3
    .forceSimulation(nodes.value)
    .force(
      "link",
      d3.forceLink(links.value).id((d) => d.id).distance(80)
    )
    .force("charge", d3.forceManyBody().strength(-200))
    .force("center", d3.forceCenter(width.value / 2, height.value / 2));

  d3.select(svgEl.value).call(
    d3.zoom().on("zoom", (event) => {
      d3.select(rootG.value).attr("transform", event.transform);
    })
  );
  d3.select(svgEl.value)
    .selectAll("g > g")
    .call(
      d3
        .drag()
        .on("start", (event, d) => {
          if (!event.active) simulation.alphaTarget(0.3).restart();
          d.fx = d.x;
          d.fy = d.y;
        })
        .on("drag", (event, d) => {
          d.fx = event.x;
          d.fy = event.y;
        })
        .on("end", (event, d) => {
          if (!event.active) simulation.alphaTarget(0);
          d.fx = null;
          d.fy = null;
        })
    )
    .on("click", (event, d) => {
      selected.value = d;
    });
}

onMounted(() => {
  if (wrap.value) {
    width.value = wrap.value.clientWidth || 900;
    height.value = wrap.value.clientHeight || 600;
  }
  if (props.entityName) loadGraph();
});

watch(() => props.entityName, (v) => {
  entityInput.value = v;
  if (v) loadGraph();
});
</script>

<style scoped>
.kg-graph-panel { font-family: system-ui, sans-serif; }
.kg-toolbar { display: flex; gap: 8px; padding: 8px; align-items: center; }
.kg-toolbar input, .kg-toolbar button, .kg-toolbar select { padding: 6px 8px; }
.kg-rel-filter { min-width: 140px; }
.kg-canvas-wrap { position: relative; width: 100%; height: 600px; border: 1px solid #eee; }
.kg-canvas-wrap svg { display: block; }
.kg-detail {
  position: absolute; top: 8px; right: 8px; width: 260px;
  background: #fff; border: 1px solid #ddd; padding: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}
.kg-detail pre { font-size: 12px; max-height: 200px; overflow: auto; }
</style>
