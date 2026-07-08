# Moving Colony 后 Local Migration 通信对象复核

## 目的

正式实验前复核 `src/tsp_mpi_moving_hdea.c` 中的 global moving colony 是否会改变下一次 local migration 的通信对象。

关注的 n=4 示例为：

```text
初始：
group 0=[0,1], group 1=[2,3]
local migration: 0<->1, 2<->3

moving 后：
group 0=[2,1], group 1=[0,3]
local migration: 2<->1, 0<->3
```

## 代码依据

当前实现中，local migration 不使用固定的物理 `groupId/localId` 作为通信对象，而是在每次 local migration 前重新查询当前逻辑位置：

```c
find_logical_position(mpiRank, &logicalGroup, &logicalPos);
sendPos = (logicalPos + 1) % subpopsPerGroup;
recvPos = (logicalPos - 1 + subpopsPerGroup) % subpopsPerGroup;
localSendTo = group_member(logicalGroup, sendPos);
localRecvFrom = group_member(logicalGroup, recvPos);
migrate_individual("local", localSendTo, localRecvFrom, LOCAL_TAG);
```

`move_colony_ring()` 会旋转 `groupMembers`：

```c
tmp = group_member(numGroups - 1, movingPosition);
for (group = numGroups - 1; group > 0; group--) {
    set_group_member(group, movingPosition, group_member(group - 1, movingPosition));
}
set_group_member(0, movingPosition, tmp);
```

因此，moving colony 更新 `groupMembers` 后，下一次 local migration 会基于更新后的逻辑分组重新计算通信对象。

## 复核运行

使用短运行触发一次 local migration、一次 moving colony，再触发下一次 local migration：

```powershell
mpiexec -n 4 bin\tsp_mpi_moving_hdea.exe data\pcb442.tsp 60 20 2 2 12345 results\_mapping_check.csv
```

参数含义：

- `nproc=4`
- `num_groups=2`
- `local_migration_interval=20`
- `local_to_global_ratio=2`
- 第 20 代发生第一次 local migration
- 第 40 代发生第二次 local migration 后触发 global moving colony
- 第 60 代发生 moving 后的下一次 local migration

实际关键输出：

```text
[rank 0] initial group_members: group 0=[0,1] group 1=[2,3]
[rank 0] local migration plan generation 20: group 0=[0->1,1->0] group 1=[2->3,3->2]
[rank 0] global moving colony generation 40: moving_position=0
[rank 0] after moving colony: group 0=[2,1] group 1=[0,3]
[rank 0] local migration plan generation 60: group 0=[2->1,1->2] group 1=[0->3,3->0]
```

该命令退出码为 `0`。

## 结论

确认：global moving colony 之后，下一次 local migration 的通信对象确实发生变化。

n=4 时，初始 local migration 对象为 `0<->1`、`2<->3`；moving 后逻辑分组变为 `group 0=[2,1]`、`group 1=[0,3]`，下一次 local migration 对象变为 `2<->1`、`0<->3`。

这说明当前 MOVING_HDEA 实现中的 moving colony 不只是记录分组变化，而是实际改变后续 local migration 的 MPI 通信对象。
