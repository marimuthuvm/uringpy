#ifndef URINGPY_SLAB_H
#define URINGPY_SLAB_H

#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    void *raw_memory;
    size_t slot_size;
    size_t total_slots;
    uint32_t *free_stack;
    int32_t top;
} slab_pool_t;

slab_pool_t* slab_pool_create(size_t total_slots, size_t slot_size);
void* slab_alloc(slab_pool_t *pool, int32_t *slot_idx);
void slab_free(slab_pool_t *pool, int32_t slot_idx);
void slab_pool_destroy(slab_pool_t *pool);

#ifdef __cplusplus
}
#endif

#endif // URINGPY_SLAB_H
