import { defineStore } from 'pinia'

import * as api from '../api/zavod'

export const useZavodStore = defineStore('zavod', {
  state: () => ({
    boards: [],
    boardId: null,
    boardTitle: '',
    nodes: [],
    edges: [],
    isLoading: false,
    loadError: '',
  }),

  getters: {
    nodeById(state) {
      const map = new Map()
      for (const node of state.nodes) map.set(node.id, node)
      return map
    },
  },

  actions: {
    async loadBoards() {
      this.boards = await api.fetchBoards()
      return this.boards
    },

    async openBoard(boardId) {
      this.isLoading = true
      this.loadError = ''
      try {
        const board = await api.fetchBoard(boardId)
        this.boardId = board.id
        this.boardTitle = board.title
        this.nodes = board.nodes
        this.edges = board.edges
      } catch {
        this.loadError = 'Не удалось загрузить доску'
      } finally {
        this.isLoading = false
      }
    },

    /** Первая загрузка раздела: список досок и открытие первой из них. */
    async init() {
      this.isLoading = true
      this.loadError = ''
      try {
        await this.loadBoards()
      } catch {
        this.loadError = 'Не удалось загрузить доски'
        this.isLoading = false
        return
      }
      if (this.boards.length) {
        await this.openBoard(this.boards[0].id)
      } else {
        this.isLoading = false
      }
    },

    async addBoard(title) {
      const board = await api.createBoard(title)
      this.boards.push(board)
      await this.openBoard(board.id)
      return board
    },

    async renameCurrentBoard(title) {
      const board = await api.renameBoard(this.boardId, title)
      this.boardTitle = board.title
      const index = this.boards.findIndex((b) => b.id === board.id)
      if (index !== -1) this.boards[index] = board
      return board
    },

    async removeCurrentBoard() {
      const removedId = this.boardId
      await api.deleteBoard(removedId)
      this.boards = this.boards.filter((b) => b.id !== removedId)
      this.boardId = null
      this.nodes = []
      this.edges = []
      if (this.boards.length) await this.openBoard(this.boards[0].id)
    },

    async addNode(payload) {
      const node = await api.createNode(this.boardId, payload)
      this.nodes.push(node)
      return node
    },

    async editNode(nodeId, payload) {
      const updated = await api.updateNode(nodeId, payload)
      const index = this.nodes.findIndex((n) => n.id === nodeId)
      if (index !== -1) this.nodes[index] = updated
      return updated
    },

    async removeNode(nodeId) {
      await api.deleteNode(nodeId)
      this.nodes = this.nodes.filter((n) => n.id !== nodeId)
      // Связи этой карточки бэкенд удалил вместе с ней — убираем и у себя.
      this.edges = this.edges.filter((e) => e.source_id !== nodeId && e.target_id !== nodeId)
    },

    /** Координаты уже применены оптимистично — здесь только сохранение. */
    async persistPositions(moves) {
      if (!moves.length) return
      await api.moveNodes(this.boardId, moves)
    },

    async addEdge(sourceId, targetId) {
      const edge = await api.createEdge(this.boardId, sourceId, targetId)
      this.edges.push(edge)
      return edge
    },

    async removeEdge(edgeId) {
      await api.deleteEdge(edgeId)
      this.edges = this.edges.filter((e) => e.id !== edgeId)
    },
  },
})
