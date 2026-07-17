#include <stdio.h>

#define CHUNK_ALLOCATED 0x8000
#define CHUNK_SIZE_MASK 0x7fff

int* HEAP_START;

// struct link_head {
//   link_head* prev;
//   link_head* next;
// };
//
// struct chunk {
//   int tag;
//   struct link_head node;
//   ...
//   int tag;
// };
//
// Heap Layout
// ===========
//
// | heap_start                 heap_start + size |
// v                                              v
// | link_head   ||                               ||
// | prev | next || tag | prev | next | ... | tag ||
//

// removeNode(list_head*) {
//   list_head->prev->next = list_head->next;
//   list_head->next->prev = list_head->prev;
// }
//
#if 1
void writeAllocatedChunk(void* pChunk, int size) {
  int tag = size | CHUNK_ALLOCATED;
  int* pLeft = pChunk;
  int* pRight = pChunk + size;
  *pLeft = tag;
  *(pRight - 1) = tag;
  puts("writeAllocatedChunk pRight - 1 ");
  printHex16((int)(pRight - 1));
}
#endif

// pChunk points to the beginning of the chunk
// prev and next point to the head_node of the prev and next chunk
void writeFreeChunk(void* pChunk, int chunkSize, void* prev, void* next) {
  puts("writeFreeChunk ");
  printHex16((int)pChunk);
  puts(" ");
  printHex16(chunkSize);
  puts("\n");
  // Write tags
  int* pLeft = pChunk;
  int* pRight = pChunk + chunkSize;
  *pLeft = chunkSize;
  *(pRight - 1) = chunkSize;
  // Write head_list prev and next
  *(pLeft + 1) = (int)prev;
  *(pLeft + 2) = (int)next;
}

void printChunk(void* pChunk) {
  int* pLeft = pChunk;
  int tag1 = *pLeft;
  int chunkSize = tag1 & CHUNK_SIZE_MASK;
  int* pRight = pChunk + chunkSize;
  int* pTag2 = pRight - 1;
  int tag2 = *pTag2;
  puts("printChunk pTag2 ");
  printHex16((int)pTag2);
  puts(" ");
  printHex16(tag2);
  puts("\n");
  int prev = *(pLeft + 1);
  int next = *(pLeft + 2);
  if (tag1 & CHUNK_ALLOCATED) {
    puts("Allocated ");
  }
  puts(" chunk at ");
  printHex16((int)pChunk);
  puts(" tags ");
  printHex16(tag1);
  puts(" ");
  printHex16(tag2);
  puts(" chunkSize ");
  printHex16(chunkSize);
  puts(" prev ");
  printHex16(prev);
  puts(" next ");
  printHex16(next);
  puts(" memblock start ");
  printHex16((int)pChunk + 6);
  puts("\n");
}

void dumpHeap() {
  puts("HEAP_START ");
  printHex16((int)HEAP_START);
  puts(" prev ");
  printHex16(*HEAP_START);
  puts(" next ");
  int* node = (int*)*(HEAP_START + 1);
  printHex16((int)node);
  puts("\n");
  while (node != HEAP_START) {
    printChunk(node-1);
    // node = node->next;
    node = (int*)*(node+1);
  }
}

// Initializes a heap starting at p and size bytes large
// The largest free block is size - 4 bytes and starts at p+4
void createHeap(void* p, int size) {
  int* heap = p;
  // Write heap free list sentinel pointing to head_list of first (only) chunk
  *heap = (int)(heap + 3);
  *(heap + 1) = (int)(heap + 3);
  HEAP_START = p;
  // TODO: don't we need occupied tags surrounding the heap?
  writeFreeChunk(p + 4, size - 4, p, p);
}

void splitChunk(void* pChunk, int chunkSize) {
  puts("splitChunk ");
  printHex16((int)pChunk);
  puts("\n");
  int* pLeft = pChunk;
  int originalSize = *pLeft;
  int newSize = originalSize - chunkSize;
  int* prev = (int*)*(pLeft + 1);
  int* next = (int*)*(pLeft + 2);
  puts("prev ");
  printHex16((int)prev);
  puts(" next");
  printHex16((int)next);
  puts("\n");

  // Shrink the original chunk upwards by chunkSize
  int* pChunkNew = pChunk + chunkSize;
  puts("pChunkNew ");
  printHex16((int)pChunkNew);
  puts("\n");
  writeFreeChunk((void*)pChunkNew, newSize, prev, next);

  // Update prev->next and next->prev for the shrunken chunk
  // *(prev->next) = pChunkNew + 2;
  *(prev + 1) = (int)(pChunkNew + 1);
  // *(next->prev) = pChunkNew + 2;
  *next = (int)(pChunkNew + 1);
}

// Note: Chunk size is size + 4
void* malloc(int size) {
  int requestedChunkSize = size + 4;
  // node = HEAP_START->next
  int* node = (int*)*(HEAP_START + 1);
  while (node != HEAP_START) {
    int* pChunk = node - 1;
    int chunkSize = *pChunk;
    if (requestedChunkSize < chunkSize) {
      splitChunk(pChunk, requestedChunkSize);
      writeAllocatedChunk(pChunk, requestedChunkSize);
      return pChunk+3;
    }
    if (requestedChunkSize > chunkSize) {
      puts("chunk to small, checking next\n");
      // node = node->next;
      node = (int*)*(node+1);
      
      // TODO: 
      // continue;
    }
    
    if (requestedChunkSize == chunkSize) {
      puts("chunk perfect size, removing from free-list\n");
      // Remove the chunk from the free list
      int* prev = (int*)*(pChunk + 1);
      int* next = (int*)*(pChunk + 2);

      // prev->next = pChunk.next
      *(prev + 1) = (int)next;
      // next->prev = pChunk.prev
      *next = (int)prev;

      writeAllocatedChunk(pChunk, requestedChunkSize);
      return pChunk+3;
    }
  }
  return 0;
}

#if 1
void free(void* p) {
  void* pVoidChunk = p - 6;
  int* pChunk = pVoidChunk;
  int* pNewChunk = pChunk;
  int chunkSize = *pChunk & CHUNK_SIZE_MASK;
  int newChunkSize = chunkSize;
  int leftTag = *(pChunk - 1);
  int* pRightTag = pVoidChunk + chunkSize;
  int rightTag = *pRightTag;
  puts("Free left and right tags ");
  printHex16((int)leftTag);
  puts(" ");
  printHex16((int)rightTag);
  puts("\n");

  if (leftTag & CHUNK_ALLOCATED == 0) {
    puts("Joining with left chunk\n");
    int leftChunkSize = leftTag & CHUNK_SIZE_MASK;
    newChunkSize = newChunkSize + leftChunkSize;
    int* pLeftChunk = pVoidChunk - leftChunkSize;
    pNewChunk = pLeftChunk;
    puts("leftChunkSize ");
    printHex16((int)leftChunkSize);
    puts("\npLeftChunk ");
    printHex16((int)pLeftChunk);
    puts("\n");

    // Remove left chunk from free list
    int* leftChunkPrev = (int*)*(pLeftChunk + 1);
    int* leftChunkNext = (int*)*(pLeftChunk + 2);

    puts("leftChunkPrev ");
    printHex16((int)leftChunkPrev);
    puts(" leftChunkNext ");
    printHex16((int)leftChunkNext);
    puts("\n");

    // leftChunk.prev->next = leftChunk.next
    *(leftChunkPrev + 1) = (int)leftChunkNext;
    // leftChunk.next->prev = leftChunk.prev
    *leftChunkNext = (int)leftChunkPrev;

    puts("heap after removal of left chunk\n");
    dumpHeap();
  }

  if (rightTag & CHUNK_ALLOCATED == 0) {
    puts("Joining with right chunk\n");
    newChunkSize = newChunkSize + rightTag & CHUNK_SIZE_MASK;
    int* pRightChunk = pVoidChunk + chunkSize;
//
// removeNode(list_head*) {
//   list_head->prev->next = list_head->next;
//   list_head->next->prev = list_head->prev;
// }

    // Remove right chunk from free list
    int* rightChunkPrev = (int*)*(pRightChunk + 1);
    int* rightChunkNext = (int*)*(pRightChunk + 2);

    puts("rightChunkPrev ");
    printHex16((int)rightChunkPrev);
    puts(" rightChunkNext ");
    printHex16((int)rightChunkNext);
    puts("\n");

    // rightChunk.prev->next = rightChunk.next
    *(rightChunkPrev + 1) = (int)rightChunkNext;
    // rightChunk.next->prev = rightChunk.prev
    *rightChunkNext = (int)rightChunkPrev;

    puts("heap after removal of right chunk\n");
    dumpHeap();
  }
  puts("newChunkSize ");
  printHex16(newChunkSize);
  puts("\npNewChunk ");
  printHex16((int)pNewChunk);
  puts("\n");

  // Add the resulting chunk first in the free list
  int* oldPrev = (int*)*HEAP_START;
  int* oldNext = (int*)*(HEAP_START + 1);
  puts("oldPrev ");
  printHex16((int)oldPrev);
  puts(" oldNext ");
  printHex16((int)oldNext);
  puts("\n");
  // HEAP_START->next = pNewChunk.head_node
  *(HEAP_START + 1) = (int)(pNewChunk + 1);
  // oldNext->prev = pNewChunk.head_node
  *oldNext = (int)(pNewChunk + 1);

  writeFreeChunk((void*)pNewChunk, newChunkSize, HEAP_START, oldNext);
}
#endif

void main() {
  puts("Creating heap\n");
  createHeap((void*)0xA000, 0x0100);
  dumpHeap();
  puts("\nCalling p1=malloc(12)\n");
  void* p1 = malloc(12);
  puts("p1 = ");
  printHex16((int)p1);
  puts("\nNew heap:\n");
  dumpHeap();

  puts("\nCalling p2=malloc(12)");
  void* p2 = malloc(12);
  puts("p2 = ");
  printHex16((int)p2);
  puts("\nNew heap:\n");
  dumpHeap();

  puts("\nCalling free(p1)\n");
  free(p1);
  puts("Heap walk:\n");
  dumpHeap();

  puts("\nCalling p3=malloc(22) Too big to re-use p1\n");
  void* p3 = malloc(22);
  puts("p3 = ");
  printHex16((int)p3);
  puts("\nNew heap:\n");
  dumpHeap();

  puts("\nCalling free(p2)\n");
  free(p2);
  puts("Heap walk:\n");
  dumpHeap();

  puts("\nCalling free(p3)\n");
  free(p3);
  puts("Heap walk:\n");
  dumpHeap();
}

