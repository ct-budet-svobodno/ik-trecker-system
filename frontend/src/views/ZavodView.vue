<script setup>
import AppSidebar from '../components/AppSidebar.vue'
</script>

<template>
  <div class="app-layout">
    <AppSidebar />

    <main class="app-main">
      <div class="app-main__header">
        <div>
          <p class="breadcrumb">ИК · ТРЕКЕР / ZAVOD</p>
          <h1>ZAVOD</h1>
          <p class="subtitle">Доска тем: карточки, связи, ответственные.</p>
        </div>
      </div>

      <div class="card placeholder">
        <p class="placeholder__title">Холст в разработке</p>
        <p class="placeholder__text">
          Раздел открыт — доступ выдан. Здесь появится бесконечная доска: карточки тем,
          связи между ними, статусы и ответственные.
        </p>
        <p class="placeholder__hint">
          Кого сюда пускать — отмечается галочкой «Доступ к ZAVOD» в разделе «Пользователи».
          Админы и руководство видят раздел без отметки.
        </p>
      </div>
    </main>
  </div>
</template>

<style scoped>
.app-layout {
  display: flex;
  min-height: 100vh;
}

.app-main {
  flex-grow: 1;
  padding: 28px 32px;
  max-width: 100%;
  overflow-x: hidden;
}

.app-main__header {
  margin-bottom: 22px;
}

.breadcrumb {
  font-size: 11px;
  letter-spacing: 0.08em;
  color: var(--text-faint);
  margin: 0 0 6px;
}

h1 {
  font-size: 22px;
  margin: 0;
  letter-spacing: 0.02em;
}

.subtitle {
  color: var(--text-muted);
  margin: 6px 0 0;
  font-size: 13px;
}

.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 18px;
}

.placeholder {
  max-width: 560px;
}

.placeholder__title {
  margin: 0 0 8px;
  font-size: 16px;
  font-weight: 600;
}

.placeholder__text {
  margin: 0;
  color: var(--text-muted);
  font-size: 14px;
}

.placeholder__hint {
  margin: 12px 0 0;
  color: var(--text-faint);
  font-size: 12px;
}
</style>
