import resolve from '@rollup/plugin-node-resolve';
import commonjs from '@rollup/plugin-commonjs';
import typescript from '@rollup/plugin-typescript';
import terser from '@rollup/plugin-terser';
import serve from 'rollup-plugin-serve';
import livereload from 'rollup-plugin-livereload';

const isDevelopment = process.env.NODE_ENV === 'development' || process.env.ROLLUP_WATCH;

const config = {
  input: 'src/index.ts',
  external: ['d3'],
  output: [
    {
      file: 'dist/index.js',
      format: 'cjs',
      exports: 'named',
      sourcemap: true,
    },
    {
      file: 'dist/index.esm.js',
      format: 'esm',
      exports: 'named',
      sourcemap: true,
    },
    {
      file: 'dist/index.umd.js',
      format: 'umd',
      name: 'BGCViewer',
      globals: {
        'd3': 'd3'
      },
      exports: 'named',
      sourcemap: true,
    },
  ],
  plugins: [
    resolve(),
    commonjs(),
    typescript({
      tsconfig: './tsconfig.json',
      declaration: true,
      outDir: 'dist',
      rootDir: 'src',
    }),
    // Only minify in production
    !isDevelopment && terser({
      format: {
        comments: false,
      },
    }),
    // Development server and live reload
    isDevelopment && serve({
      open: true,
      openPage: '/dev.html',
      contentBase: ['dist', './'],
      host: 'localhost',
      port: 8080,
    }),
    isDevelopment && livereload({
      watch: ['dist', '.'],
      verbose: true,
    }),
  ].filter(Boolean),
};

export default config;
