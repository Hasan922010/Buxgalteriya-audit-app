interface CacheEntry<T> {
  data: T;
  expiresAt: number;
  tags: string[];
}

class MemoryCache {
  private cache = new Map<string, CacheEntry<any>>();

  get<T>(key: string): T | null {
    const entry = this.cache.get(key);
    if (!entry) return null;

    if (Date.now() > entry.expiresAt) {
      this.cache.delete(key);
      return null;
    }

    return entry.data as T;
  }

  set<T>(key: string, data: T, ttlSeconds: number = 60, tags: string[] = []): void {
    const expiresAt = Date.now() + ttlSeconds * 1000;
    this.cache.set(key, { data, expiresAt, tags });
  }

  invalidateTags(tagsToInvalidate: string[]): void {
    const set = new Set(tagsToInvalidate);
    const keysToDelete: string[] = [];
    this.cache.forEach((entry, key) => {
      if (entry.tags.some(tag => set.has(tag))) {
        keysToDelete.push(key);
      }
    });
    keysToDelete.forEach((k) => this.cache.delete(k));
  }

  clear(): void {
    this.cache.clear();
  }

  invalidateAll(): void {
    this.clear();
  }
}

export const appCache = new MemoryCache();
