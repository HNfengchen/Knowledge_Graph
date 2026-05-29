# graphpanel.vue 集成说明

单文件 Vue 3 组件，用 D3 v7 力导向图渲染知识图谱子图。

## 在已有 Vue 工程中使用

```bash
npm i d3
```

```vue
<script setup>
import GraphPanel from "./graphpanel.vue";
</script>
<template>
  <GraphPanel
    api-base-url="http://localhost:8000"
    entity-name="张三"
    :depth="2"
    auth-token="<JWT>"
  />
</template>
```

## 纯 HTML + CDN 方式

```html
<script type="importmap">
{ "imports": { "vue": "https://unpkg.com/vue@3/dist/vue.esm-browser.js",
                "d3": "https://unpkg.com/d3@7/dist/d3.min.js" } }
</script>
```

挂载方式同上。

## API 约定

- 路径：`POST {apiBaseUrl}/api/v1/kg/query`
- 请求体：`{ "entity_name": string, "depth": 1..3, "relation_types": string[] | null }`
- 响应：`{ "code": 200, "msg": "success", "data": { "nodes": [...], "links": [...] } }`
  - `nodes[i]`: `{ id, name, type, props }`
  - `links[i]`: `{ source, target, relation, weight }`
