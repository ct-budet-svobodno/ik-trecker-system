import { defineStore } from 'pinia'

import {
  addComment,
  assignRole,
  createPost,
  deleteComment,
  deletePost,
  fetchPost,
  fetchPosts,
  resolveComment,
  unassignRole,
  updatePost,
} from '../api/editorial'

export const useEditorialStore = defineStore('editorial', {
  state: () => ({
    posts: [],
    isLoading: false,
    loadError: '',
    currentPost: null,
  }),

  actions: {
    async load({ dateFrom, dateTo }) {
      this.isLoading = true
      this.loadError = ''
      try {
        this.posts = await fetchPosts({ dateFrom, dateTo })
      } catch {
        this.loadError = 'Не удалось загрузить календарь Редакции'
      } finally {
        this.isLoading = false
      }
    },

    async create(payload) {
      const post = await createPost(payload)
      this.posts.push(post)
      return post
    },

    async remove(postId) {
      await deletePost(postId)
      this.posts = this.posts.filter((p) => p.id !== postId)
      if (this.currentPost?.id === postId) this.currentPost = null
    },

    // --- Карточка поста ---
    async loadPost(postId) {
      this.currentPost = await fetchPost(postId)
      return this.currentPost
    },

    _sync(post) {
      this.currentPost = post
      const index = this.posts.findIndex((p) => p.id === post.id)
      if (index !== -1) this.posts[index] = post
      return post
    },

    async update(postId, payload) {
      return this._sync(await updatePost(postId, payload))
    },

    async assign(postId, role, userId = null) {
      return this._sync(await assignRole(postId, role, userId))
    },

    async unassign(postId, role) {
      return this._sync(await unassignRole(postId, role))
    },

    async comment(postId, payload) {
      return this._sync(await addComment(postId, payload))
    },

    async resolve(postId, commentId, resolved) {
      return this._sync(await resolveComment(postId, commentId, resolved))
    },

    async removeComment(postId, commentId) {
      return this._sync(await deleteComment(postId, commentId))
    },
  },
})
