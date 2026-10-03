#include "slab.h"
#include <sys/mman.h>
#include <string.h>

slab_pool_t* slab_pool_create(size_t total_slots, size_t slot_size) {
    slab_pool_t *pool = (slab_pool_t*)malloc(sizeof(slab_pool_t));
    if (!pool) return NULL;

    pool->slot_size = slot_size;
    pool->total_slots = total_slots;
    pool->top = (int32_t)total_slots - 1;

    size_t total_bytes = total_slots * slot_size;
    if (posix_memalign(&pool->raw_memory, 4096, total_bytes) != 0) {
        free(pool);
        return NULL;
    }
    memset(pool->raw_memory, 0, total_bytes);

    pool->free_stack = (uint32_t*)malloc(total_slots * sizeof(uint32_t));
    if (!pool->free_stack) {
        free(pool->raw_memory);
        free(pool);
        return NULL;
    }

    for (size_t i = 0; i < total_slots; i++) {
        pool->free_stack[i] = (uint32_t)(total_slots - 1 - i);
    }

    return pool;
}

void* slab_alloc(slab_pool_t *pool, int32_t *slot_idx) {
    if (!pool || pool->top < 0) {
        *slot_idx = -1;
        return NULL;
    }

    uint32_t idx = pool->free_stack[pool->top--];
    *slot_idx = (int32_t)idx;
    return (char*)pool->raw_memory + (idx * pool->slot_size);
}

void slab_free(slab_pool_t *pool, int32_t slot_idx) {
    if (!pool || slot_idx < 0 || (size_t)slot_idx >= pool->total_slots) return;
    if (pool->top < (int32_t)pool->total_slots - 1) {
        pool->free_stack[++pool->top] = (uint32_t)slot_idx;
    }
}

void slab_pool_destroy(slab_pool_t *pool) {
    if (!pool) return;
    if (pool->raw_memory) free(pool->raw_memory);
    if (pool->free_stack) free(pool->free_stack);
    free(pool);
}
