function facemorph(infile1, infile2, outfile, points1, points2, ratio)

img1 = imread(infile1);
img2 = imread(infile2);

assert(all(size(img1) == size(img2)));
assert(all(size(points1) == size(points2)));
img1 = double(img1);
img2 = double(img2);
[h, w, nchannels] = size(img1);
points1 = [points1; 1,1; 1,h; w,1; w,h];
points2 = [points2; 1,1; 1,h; w,1; w,h];

[X, Y] = meshgrid(1:w, 1:h);
I = cell(nchannels, 1);
for channel = 1:nchannels
    I{channel} = sub2ind([h, w, nchannels], Y(:), X(:), ones(h*w,1)*channel);
end

p = points1 + ratio*(points2-points1);
tri = delaunay(p(:,1), p(:,2), 'QJ');
n = size(tri, 1);
T = tsearch(p(:,1), p(:,2), tri, X(:), Y(:));

src = cell(n, 1);
dst = cell(n, 1);
mix = cell(nchannels, n);

for i = 1:n
    Xinv = inv([p(tri(i,:),1), p(tri(i,:),2), ones(3,1)]');
    M1 = [points1(tri(i,:),1), points1(tri(i,:),2), ones(3,1)]' * Xinv;
    M2 = [points2(tri(i,:),1), points2(tri(i,:),2), ones(3,1)]' * Xinv;
    f = find(T == i);
    dummy = [X(f), Y(f), ones(length(f),1)]';
    src{i} = M1 * dummy;
    dst{i} = M2 * dummy;
    for c = 1:nchannels
        mix{c, i} = I{c}(f);
    end
end

src = cat(2, src{:});
dst = cat(2, dst{:});
output = ones(h, w, nchannels);

for c = 1:nchannels
    output(cat(1, mix{c,:})) = ...
        (1-ratio)*interp2(img1(:,:,c), src(1,:), src(2,:), 'cubic', 1) + ...
        ratio*interp2(img2(:,:,c), dst(1,:), dst(2,:), 'cubic', 1);
end

output(find(output < 0)) = 0;
output = output / max(output(:));

imwrite(output, outfile);

endfunction
