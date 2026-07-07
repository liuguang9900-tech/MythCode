"""
归并排序（Merge Sort）算法实现与测试。

归并排序采用分治策略，时间复杂度 O(n log n)，空间复杂度 O(n)，稳定排序。
"""

from typing import TypeVar, Optional

T = TypeVar("T")


def merge_sort(arr: list[T]) -> list[T]:
    """
    归并排序主函数（非原地排序，返回新列表）。

    分治三步骤：
    1. 分解：将数组递归地分成两半，直到长度为 1
    2. 解决：合并两个有序子数组
    3. 合并：在合并阶段完成排序

    Args:
        arr: 待排序的列表。

    Returns:
        排序后的新列表，原列表不变。

    Examples:
        >>> merge_sort([3, 1, 2])
        [1, 2, 3]
        >>> merge_sort([])
        []
    """
    if len(arr) <= 1:
        return arr[:]  # 返回副本，不修改原列表

    mid: int = len(arr) // 2
    left: list[T] = merge_sort(arr[:mid])
    right: list[T] = merge_sort(arr[mid:])

    return _merge(left, right)


def _merge(left: list[T], right: list[T]) -> list[T]:
    """
    合并两个已排序的子列表。

    使用双指针法依次比较两个子列表的当前元素，
    将较小的元素放入结果列表中。

    Args:
        left: 已排序的左半部分。
        right: 已排序的右半部分。

    Returns:
        合并后的有序列表。
    """
    result: list[T] = []
    i: int = 0  # 左指针
    j: int = 0  # 右指针
    len_left: int = len(left)
    len_right: int = len(right)

    # 双指针遍历，比较并合并
    while i < len_left and j < len_right:
        if left[i] <= right[j]:
            result.append(left[i])
            i += 1
        else:
            result.append(right[j])
            j += 1

    # 将剩余元素追加到结果（最多只有一个子列表还有剩余）
    result.extend(left[i:])
    result.extend(right[j:])

    return result


def merge_sort_inplace(arr: list[T], left: int = 0, right: Optional[int] = None) -> None:
    """
    归并排序原地版本，直接修改原列表。

    Args:
        arr: 待排序的列表（原地修改）。
        left: 当前排序区间的左边界索引。
        right: 当前排序区间的右边界索引（不含）。
    """
    if right is None:
        right = len(arr)

    if right - left <= 1:
        return

    mid: int = (left + right) // 2
    merge_sort_inplace(arr, left, mid)
    merge_sort_inplace(arr, mid, right)

    _merge_inplace(arr, left, mid, right)


def _merge_inplace(arr: list[T], left: int, mid: int, right: int) -> None:
    """
    原地合并两个已排序的连续子数组 arr[left:mid] 和 arr[mid:right]。

    先复制左半部分作为临时数组，再按合并逻辑写回 arr。
    """
    temp: list[T] = arr[left:mid]  # 复制左半部分作为临时空间
    i: int = 0           # temp 的指针
    j: int = mid         # 右半部分在 arr 中的起始指针
    k: int = left        # 写回 arr 的目标指针
    len_temp: int = len(temp)

    while i < len_temp and j < right:
        if temp[i] <= arr[j]:
            arr[k] = temp[i]
            i += 1
        else:
            arr[k] = arr[j]
            j += 1
        k += 1

    # 剩余元素：只有 temp 可能有剩余（右半部分已在 arr 原位）
    while i < len_temp:
        arr[k] = temp[i]
        i += 1
        k += 1


# ============================
# 测试代码
# ============================

def _run_tests() -> None:
    """运行所有测试用例，打印通过/失败统计。"""
    passed: int = 0
    failed: int = 0

    def assert_equal(actual, expected, case_name: str = "") -> None:
        nonlocal passed, failed
        if actual == expected:
            passed += 1
            print(f"  ✅ {case_name}")
        else:
            failed += 1
            print(f"  ❌ {case_name}: 期望 {expected!r}，实际 {actual!r}")

    # ---- 非原地版本测试 ----
    print("\n=== 非原地归并排序 (merge_sort) ===")

    # 空列表
    assert_equal(merge_sort([]), [], "空列表")

    # 单元素
    assert_equal(merge_sort([42]), [42], "单元素列表")

    # 两个元素
    assert_equal(merge_sort([2, 1]), [1, 2], "两元素逆序")
    assert_equal(merge_sort([1, 2]), [1, 2], "两元素已有序")

    # 奇数长度
    assert_equal(merge_sort([3, 1, 4, 1, 5, 9, 2]),
                 [1, 1, 2, 3, 4, 5, 9], "奇数长度列表")

    # 偶数长度
    assert_equal(merge_sort([5, 3, 8, 1, 2, 7]),
                 [1, 2, 3, 5, 7, 8], "偶数长度列表")

    # 含重复元素
    assert_equal(merge_sort([2, 3, 2, 1, 3, 1]),
                 [1, 1, 2, 2, 3, 3], "含重复元素")

    # 已排序列表
    assert_equal(merge_sort([1, 2, 3, 4, 5]),
                 [1, 2, 3, 4, 5], "已排序列表")

    # 完全逆序
    assert_equal(merge_sort([5, 4, 3, 2, 1]),
                 [1, 2, 3, 4, 5], "完全逆序列表")

    # 负数和零
    assert_equal(merge_sort([0, -1, 3, -5, 2]),
                 [-5, -1, 0, 2, 3], "含负数和零")

    # 浮点数
    assert_equal(merge_sort([3.5, 1.2, 2.8, 1.1]),
                 [1.1, 1.2, 2.8, 3.5], "浮点数列表")

    # 字符串
    assert_equal(merge_sort(["banana", "apple", "cherry"]),
                 ["apple", "banana", "cherry"], "字符串排序")

    # 原列表不被修改
    original = [3, 1, 2]
    result = merge_sort(original)
    assert_equal(original, [3, 1, 2], "原列表不被修改")

    # 大数据量压力测试（快速验证不会崩溃）
    large: list[int] = list(range(1000, 0, -1))
    assert_equal(merge_sort(large), list(range(1, 1001)), "大数据量 1000 个元素")

    # ---- 原地版本测试 ----
    print("\n=== 原地归并排序 (merge_sort_inplace) ===")

    def sort_and_get(arr: list[T]) -> list[T]:
        merge_sort_inplace(arr)
        return arr

    assert_equal(sort_and_get([]), [], "原地-空列表")
    assert_equal(sort_and_get([1]), [1], "原地-单元素")
    assert_equal(sort_and_get([3, 1, 4, 1, 5, 9, 2]),
                 [1, 1, 2, 3, 4, 5, 9], "原地-奇数长度")
    assert_equal(sort_and_get([5, 3, 8, 2, 7]),
                 [2, 3, 5, 7, 8], "原地-偶数长度")
    assert_equal(sort_and_get([1, 2, 3, 4, 5]),
                 [1, 2, 3, 4, 5], "原地-已有序")

    # ---- doctest（仅在有 doctest 时启用） ----
    print("\n=== doctest ===")
    import doctest
    doc_result = doctest.testmod(verbose=False)
    if doc_result.failed == 0:
        print(f"  ✅ doctest 全部通过 ({doc_result.attempted} 项)")
    else:
        print(f"  ❌ doctest 有 {doc_result.failed} 项失败")

    # ---- 总结 ----
    print(f"\n{'=' * 40}")
    print(f"测试完成: {passed} 通过, {failed} 失败, {doc_result.attempted} doctest")
    if failed > 0 or doc_result.failed > 0:
        print("❌ 存在失败用例！")
    else:
        print("🎉 全部通过！")


if __name__ == "__main__":
    # 交互式演示
    sample: list[int] = [38, 27, 43, 3, 9, 82, 10]
    print(f"原始列表: {sample}")
    print(f"非原地排序: {merge_sort(sample)}")
    print(f"原列表仍是: {sample}")

    # 原地排序演示
    inplace_sample: list[int] = [38, 27, 43, 3, 9, 82, 10]
    merge_sort_inplace(inplace_sample)
    print(f"原地排序后: {inplace_sample}")

    # 运行测试
    _run_tests()
