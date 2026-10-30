"""Numeric boundary cases needed by the standard-library model converters."""
import math
import random
import struct
import unittest

from tools.derive import arraymath as a


class Arrays(unittest.TestCase):
    def test_float32_rounds_each_operation(self):
        value = a.array([16777216, 16777218], a.float32)
        self.assertEqual((value + 1).tolist(), [16777216, 16777220])
        self.assertEqual(((value + 1) - value).tolist(), [0, 2])
        self.assertEqual(a.array([-0.], a.float32).tobytes(), struct.pack('<I', 0x80000000))

    def test_float32_scalar_and_pairwise_sum_rounding(self):
        value = a.array([.7, .9], a.float32)
        self.assertEqual((value * .123456789).tobytes().hex(), 'd7fcb03d398ee33d')
        # A float64 accumulator would retain the small terms here.
        self.assertEqual(a.array([1e9] + [1] * 15 + [-1e9], a.float32).sum(), 0.)

    def test_integer_writes_wrap(self):
        value = a.array([0, 255, 256, -1], a.uint8)
        self.assertEqual(value.tobytes(), b'\0\xff\0\xff')
        self.assertEqual((value + 1).tolist(), [1, 0, 1, 0])
        self.assertEqual(a.array([32768, 65535], a.int16).tolist(), [-32768, -1])

    def test_views_and_mask_assignment(self):
        value = a.array([[0, 1, 2], [3, 4, 5]])
        value[:, 1] += 7
        self.assertEqual(value.tolist(), [[0, 8, 2], [3, 11, 5]])
        view = value[:, 1:]
        view[view > 4] = -1
        self.assertEqual(value.tolist(), [[0, -1, 2], [3, -1, -1]])
        value[[0, 1], [2, 0]] = [20, 30]
        self.assertEqual(value.tolist(), [[0, -1, 20], [30, -1, -1]])

    def test_broadcast_and_index_order(self):
        value = a.array([[0, 1, 2], [3, 4, 5]])
        self.assertEqual((value + [10, 20, 30]).tolist(), [[10, 21, 32], [13, 24, 35]])
        self.assertEqual(value[a.ix_([1, 0], [2, 0])].tolist(), [[5, 3], [2, 0]])
        self.assertEqual(value[value > 1].tolist(), [2, 3, 4, 5])
        self.assertEqual(value.T.tolist(), [[0, 3], [1, 4], [2, 5]])

    def test_concatenated_vertex_cloud_promotes_fractional_coordinates(self):
        base = a.array([[1, 2, 3]])
        rotated = a.array([[1.25, -2.75, 3.5]])
        result = a.concatenate([base, rotated])
        self.assertIs(result.dtype, a.float64)
        self.assertEqual(result.tolist(), [[1., 2., 3.], [1.25, -2.75, 3.5]])
        self.assertIs(a.concatenate([a.array([1], a.float32), a.array([1], a.uint16)]).dtype, a.float32)
        self.assertIs(a.concatenate([a.array([1], a.float32), a.array([1], a.int32)]).dtype, a.float64)
        self.assertIs(a.concatenate([a.array([1], a.uint16), a.array([-1], a.int16)]).dtype, a.int32)

    def test_reductions_and_ties(self):
        value = a.array([[2., -3., -3.], [7., 1., 7.]])
        self.assertEqual(value.argmin(1).tolist(), [1, 1])
        self.assertEqual(value.argmax(1).tolist(), [0, 0])
        self.assertEqual(value.sum(0).tolist(), [9, -2, 4])
        self.assertEqual(value.mean(1).tolist(), [-4/3, 5])
        self.assertEqual(value.max(1, keepdims=True).shape, (2, 1))

    def test_matrix_inverse_and_polar_factor(self):
        rng = random.Random(284)
        for _ in range(30):
            matrix = a.array([[rng.uniform(-2, 2) for _ in range(3)] for _ in range(3)])
            inverse = a.linalg.inv(matrix)
            self.assertLess(abs(matrix @ inverse - a.eye(3)).max(), 1e-12)
            u, s, vt = a.linalg.svd(matrix)
            self.assertLess(abs(u @ a.diag(s) @ vt - matrix).max(), 1e-12)
            self.assertLess(abs(u.T @ u - a.eye(3)).max(), 1e-12)
            self.assertLess(abs(vt @ vt.T - a.eye(3)).max(), 1e-12)

    def test_reflection_uses_lapack_tie_order_after_a_swap(self):
        u, scale, vt = a.linalg.svd(a.diag([1., 1., -6.]))
        u[:, -1] = -u[:, -1]
        self.assertEqual(scale.tolist(), [6., 1., 1.])
        self.assertEqual((u @ vt).tolist(), [[-1., 0., 0.], [0., 1., 0.], [0., 0., -1.]])

    def test_small_matrix_products_preserve_operation_order(self):
        rng = random.Random(261)
        for size in (3, 4):
            for _ in range(12):
                left = a.array([[rng.uniform(-10, 10) for _ in range(size)] for _ in range(size)])
                right = a.array([[rng.uniform(-10, 10) for _ in range(size)] for _ in range(size)])
                expected = []
                for row in left:
                    out = []
                    for col in right.T:
                        total = 0.0
                        for x, y in zip(row, col): total += x*y
                        out.append(total)
                    expected.append(out)
                self.assertEqual((left @ right).tobytes(), a.array(expected).tobytes())

    def test_batched_small_products_match_individual_products(self):
        rng = random.Random(409)
        for size in (3, 4):
            matrices = a.array([[[rng.uniform(-10, 10) for _ in range(size)] for _ in range(size)] for _ in range(5)])
            right = a.array([[rng.uniform(-10, 10) for _ in range(size)] for _ in range(size)])
            expected = a.stack([matrix @ right for matrix in matrices])
            self.assertEqual((matrices @ right).tobytes(), expected.tobytes())

    def test_homogeneous_point_transform_preserves_sum_order(self):
        rng = random.Random(91)
        matrices = a.array([[[rng.uniform(-10, 10) for _ in range(4)] for _ in range(4)] for _ in range(3)])
        points = a.array([[rng.uniform(-10, 10) for _ in range(4)] for _ in range(7)])
        expected = []
        for matrix in matrices:
            row = []
            for point in points:
                values = []
                for coeffs in matrix:
                    total = 0.0
                    for x, y in zip(coeffs, point): total += x * y
                    values.append(total)
                row.append(values)
            expected.append(row)
        actual = a.einsum('fij,nj->fni', matrices, points)
        self.assertEqual(actual.tobytes(), a.array(expected).tobytes())
        # Last-axis reductions must also work on a view skipping column four.
        self.assertEqual(actual[:, :, :3].sum(2).tolist(),
                         [[((-0.0 + p[0]) + p[1]) + p[2] for p in frame] for frame in expected])

    def test_point_norms_keep_sequential_square_sum(self):
        points = a.array([[1e8, 1., 1.], [3., 4., 0.]])
        self.assertEqual(a.linalg.norm(points, axis=1).tolist(), [1e8, 5.])
        self.assertEqual(a.linalg.norm(points[0]), 1e8)
        self.assertEqual(a.linalg.norm(points, axis=1, keepdims=True).tolist(), [[1e8], [5.]])

    def test_fused_rig_error_preserves_vector_expression(self):
        from tools.rigfix import _motion_error
        rng = random.Random(431)
        for _ in range(5):
            matrices = a.array([[[rng.uniform(-10, 10) for _ in range(4)] for _ in range(4)] for _ in range(3)])
            points = a.array([[rng.uniform(-10, 10) for _ in range(4)] for _ in range(7)])
            target = a.array([[[rng.uniform(-10, 10) for _ in range(3)] for _ in range(7)] for _ in range(3)])
            actual = a.einsum('fij,nj->fni', matrices, points)[:, :, :3]
            distance = a.linalg.norm(actual - target, axis=2) / 125.5
            expected = (a.sqrt((distance ** 2).mean()), distance.max())
            self.assertEqual(_motion_error(matrices, points, target, 125.5), expected)

    def test_cached_inverse_results_are_independent(self):
        value = a.diag([1., 2., 3.])
        inverse = a.linalg.pinv(value)
        expected = inverse.tobytes()
        inverse[:] = 0
        self.assertEqual(a.linalg.pinv(value).tobytes(), expected)

    def test_singular_hidden_bone(self):
        matrix = a.diag([0., 1., 2.])
        self.assertEqual(a.linalg.pinv(matrix).tolist(), [[0., 0., 0.], [0., 1., 0.], [0., 0., .5]])
        with self.assertRaises(a.linalg.LinAlgError):
            a.linalg.inv(matrix)

    def test_sine_cosine_fit(self):
        angles = [i * 2 * math.pi / 40 for i in range(40)]
        design = a.column_stack([[math.sin(x) for x in angles], [math.cos(x) for x in angles]])
        target = design @ [3.5, -2.25]
        result = a.linalg.lstsq(design, target)[0]
        self.assertLess(abs(result - [3.5, -2.25]).max(), 1e-14)


if __name__ == '__main__':
    unittest.main()
