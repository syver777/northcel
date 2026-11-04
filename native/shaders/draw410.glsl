#version 410 core
// NorthCel native rasteriser: even-odd winding parity on an N x N subpixel
// grid, 8-row band acceleration, fixed box integration. No clock, texture
// noise, hash or random jitter is read: every pixel is a pure function of the
// frame's vector edges, colours and the paper grain applied by the host.
uniform samplerBuffer edgeTex;
uniform isamplerBuffer spanTex;
uniform samplerBuffer colorTex;
uniform int bandCount;
uniform int layerCount;
uniform int aa;
uniform vec2 canvas;
out vec4 fragColor;

void main() {
  // gl_FragCoord is bottom-up; NorthCel's origin is the top-left corner.
  vec2 origin = vec2(floor(gl_FragCoord.x), canvas.y - 1.0 - floor(gl_FragCoord.y));
  vec3 sum = vec3(0.0);
  int grid = aa < 1 ? 1 : aa;
  for (int sy = 0; sy < grid; ++sy) {
    for (int sx = 0; sx < grid; ++sx) {
      vec2 p = origin + (vec2(float(sx), float(sy)) + 0.5) / float(grid);
      int band = int(floor(p.y / 8.0));
      if (band < 0) band = 0;
      if (band >= bandCount) band = bandCount - 1;
      vec3 value = texelFetch(colorTex, 0).rgb;
      for (int l = 0; l < layerCount; ++l) {
        ivec2 span = texelFetch(spanTex, l * bandCount + band).xy;
        bool inside = false;
        for (int i = span.x; i < span.y; ++i) {
          vec4 e = texelFetch(edgeTex, i);
          if ((e.y > p.y) != (e.w > p.y)) {
            float crossX = e.x + (p.y - e.y) * (e.z - e.x) / (e.w - e.y);
            if (p.x < crossX) inside = !inside;
          }
        }
        if (inside) value = texelFetch(colorTex, 1 + l).rgb;
      }
      sum += value;
    }
  }
  fragColor = vec4(sum / float(grid * grid), 1.0);
}
