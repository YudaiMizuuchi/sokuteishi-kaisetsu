// 保存層。localStorage 版と、ログイン中だけクラウド（Supabase）へも書く版を、同じ関数群（load／add／removeAll）で使う。
import { fetchAll, insertMany, deleteAll, deleteByIds } from "./cloud.js";

const KEY = "sokuteishi.practice.v1";

function memoryStorage() {
  const m = new Map();
  return { getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, v), removeItem: (k) => m.delete(k) };
}

/** localStorage に、記録の配列を持つ。使えないとき（プライベートブラウズなど）は、ページを開いている間だけ覚える。 */
export function createLocalStore(storage, key = KEY) {
  let persistent = true;
  if (!storage) {
    try { storage = window.localStorage; storage.setItem(key + ".t", "1"); storage.removeItem(key + ".t"); }
    catch { storage = memoryStorage(); persistent = false; }
  }
  const read = () => {
    try { const v = JSON.parse(storage.getItem(key) || "[]"); return Array.isArray(v) ? v : []; }
    catch { return []; }
  };
  return {
    kind: "local", persistent, storage,
    async load() { return read(); },
    async add(attempt) { const a = read(); a.push(attempt); storage.setItem(key, JSON.stringify(a)); },
    async removeAll() { storage.removeItem(key); },
    async remove(ids) { const drop = new Set(ids); storage.setItem(key, JSON.stringify(read().filter((a) => !drop.has(a.id)))); },
  };
}

const pendingKey = (userId) => `sokuteishi.practice.pending.${userId}.v1`;
const dedupe = (rows) => { const m = new Map(); for (const r of rows) m.set(r.id, r); return [...m.values()]; };

/**
 * 保存層の本体。ログインしていなければ localStorage だけ。
 * ログイン中は、クラウドに書く。書けなかった分（通信できない・一時停止中など）は、この端末の「未送信」に溜めて、あとで送る。
 */
export function createStore(local) {
  let client = null, userId = null, pending = null;
  const store = {
    persistent: local.persistent,
    get signedIn() { return !!userId; },
    get kind() { return userId ? "cloud" : "local"; },

    setUser(c, id) { client = c; userId = id; pending = createLocalStore(local.storage, pendingKey(id)); },
    clearUser() { client = null; userId = null; pending = null; },

    /** ログイン直後：この端末の記録をクラウドへ取り込み、未送信の分を送る。成功したら、端末側の記録は消す（共用の端末で、他の人の記録が混ざらないように）。 */
    async syncAfterLogin() {
      const out = { imported: 0, flushed: 0, error: null };
      try {
        const mine = await local.load();
        if (mine.length) { await insertMany(client, mine); await local.removeAll(); out.imported = mine.length; }
        const left = await pending.load();
        if (left.length) { await insertMany(client, left); await pending.removeAll(); out.flushed = left.length; }
      } catch (e) { out.error = e; }
      return out;
    },

    async load() {
      if (!userId) return local.load();
      const left = await pending.load();
      try { return dedupe([...(await fetchAll(client)), ...left]); }
      catch (e) { const err = new Error("クラウドの記録を読み込めませんでした"); err.cause = e; err.fallback = left; throw err; }
    },

    /** 戻り値："local"（この端末）／"cloud"（クラウドに保存）／"pending"（クラウドに送れず、この端末に溜めた）／"full"（保存の上限に達していて、保存しなかった） */
    async add(attempt) {
      if (!userId) { await local.add(attempt); return "local"; }
      try { await insertMany(client, [attempt]); return "cloud"; }
      catch (e) {
        if (e && e.code === "42501") return "full";   // 行レベルセキュリティに拒否された＝1人あたりの上限。溜めても送れないので、溜めない
        await pending.add(attempt); return "pending";
      }
    },

    /** 古い記録を消す（間引き）。失敗しても、演習は続ける。 */
    async remove(ids) {
      if (!ids.length) return;
      if (!userId) return local.remove(ids);
      await pending.remove(ids);
      await deleteByIds(client, ids);
    },

    async removeAll() {
      if (!userId) return local.removeAll();
      await deleteAll(client);
      await pending.removeAll();
    },

    async pendingCount() { return pending ? (await pending.load()).length : 0; },
  };
  return store;
}
